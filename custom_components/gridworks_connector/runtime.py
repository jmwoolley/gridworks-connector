"""HA observation bindings and lifecycle; no equipment control interface."""

from __future__ import annotations

import asyncio
import math
import time
from datetime import timedelta
from uuid import uuid4

from homeassistant.components import persistent_notification
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval

from .const import DOMAIN, HEARTBEAT_SECONDS, KINDS
from .engine import ShadowEngine
from .journal import Journal
from .peer import ShadowPeer
from .protocol import (
    Availability,
    Gap,
    Message,
    ModeEvent,
    Observations,
    Reading,
    Resource,
    ServiceStatus,
    WeatherSelection,
)
from .transport import ShadowMqtt


def clock_ms():
    return int(time.time() * 1000)


def read_value(state, binding, now_ms):
    """A cached value retains its HA-report timestamp; never invent acquisition time."""
    if state is None:
        return None, None, "unknown"
    value = state.attributes.get(binding["attribute"]) if binding.get("attribute") else state.state
    stamp = getattr(state, "last_reported", None) or state.last_updated
    observed = int(stamp.timestamp() * 1000) if stamp else None
    if value in ("unknown", "unavailable", None):
        return None, observed, "unavailable" if value == "unavailable" else "unknown"
    if binding["kind"] == "current_mode":
        value = str(value)
    elif isinstance(value, str) and value.lower() in ("on", "off", "true", "false"):
        value = value.lower() in ("on", "true")
    else:
        try:
            value = float(value)
            if not math.isfinite(value):
                return None, observed, "invalid"
        except TypeError, ValueError:
            value = str(value)
    if binding["kind"] == "temperature":
        actual_unit = state.attributes.get("unit_of_measurement")
        if actual_unit and actual_unit != binding.get("unit"):
            return None, observed, "invalid"
        if isinstance(value, (str, bool)):
            return None, observed, "invalid"
    age = now_ms - observed if observed is not None else None
    quality = (
        "stale"
        if age is not None and age > binding.get("stale_seconds", 300) * 1000
        else "reported"
    )
    return value, observed, quality


class Runtime:
    def __init__(self, hass, entry, profile):
        self.hass, self.entry, self.profile = hass, entry, profile
        self.signal = f"{DOMAIN}_{entry.entry_id}"
        self.lock = asyncio.Lock()
        self.journal = None
        self.peer_journal = None
        self.engine = None
        self.peer = None
        self.transport = None
        self.closed = False
        self.connected = False
        self.last_error = None
        self.last_mode = object()
        self.mode_since = None
        self.last_flush = 0
        self.unsubscribers = []
        self.tasks = set()
        self.last_snapshot = None
        self.last_protocol_check = "not_run"

    async def start(self):
        bindings = self.profile["bindings"]
        resource = Resource(
            name=self.profile["name"],
            channels=[
                {
                    k: v
                    for k, v in b.items()
                    if k not in ("entity_id", "attribute", "registry_id", "label", "stale_seconds")
                }
                for b in bindings
            ],
            modes=[
                {k: v for k, v in m.items() if k != "state_value"} for m in self.profile["modes"]
            ],
            meters=self.profile["meters"],
            services=self.profile["services"],
            location=self.profile["location"],
            capabilities=["shadow_only", "draft_protocol", "full_communication_v1"],
        )
        path = self.hass.config.path(".storage", f"{DOMAIN}_{self.entry.entry_id}.sqlite")

        def build():
            self.journal = Journal(path)
            self.engine = ShadowEngine(
                self.profile["resource_id"],
                self.profile["revision"],
                resource,
                self.journal,
                clock_ms,
            )

            if self.profile["transport"]["mode"] == "local_demo":
                self.peer_journal = Journal(
                    self.hass.config.path(".storage", f"{DOMAIN}_{self.entry.entry_id}_peer.sqlite")
                )
                self.peer = ShadowPeer(clock_ms, self.peer_journal)

        await self.hass.async_add_executor_job(build)
        if self.profile["transport"]["mode"] == "local_demo":
            self.connected = True
        else:
            try:
                self.transport = await self.hass.async_add_executor_job(
                    ShadowMqtt,
                    self.profile["transport"],
                    self.queue_incoming,
                    self.queue_connection,
                )
                await self.hass.async_add_executor_job(self.transport.start)
            except (OSError, ValueError) as err:
                self.last_error = f"transport_setup_{type(err).__name__}"
                # Local observation/status still load; cloud auth never unloads the local entry.
        ids = [b["entity_id"] for b in bindings]
        self.unsubscribers.append(
            async_track_state_change_event(self.hass, ids, self._state_changed)
        )
        self.unsubscribers.append(
            async_track_time_interval(
                self.hass, self._periodic, timedelta(seconds=HEARTBEAT_SECONDS)
            )
        )
        await self.exchange(lambda: [self.engine.message("resource.config", resource)])
        await self.snapshot()

    @callback
    def _state_changed(self, event):
        if not self.closed:
            self.spawn(self.snapshot({event.data["entity_id"]: event.data.get("new_state")}))

    @callback
    def _periodic(self, now):
        if not self.closed:
            self.spawn(self.tick())

    def spawn(self, coroutine):
        task = self.hass.async_create_task(coroutine)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task

    def queue_incoming(self, body):
        self.hass.loop.call_soon_threadsafe(
            lambda: None if self.closed else self.spawn(self.incoming(body))
        )

    def queue_connection(self, connected):
        self.hass.loop.call_soon_threadsafe(
            lambda: None if self.closed else self.spawn(self.connection_changed(connected))
        )

    async def connection_changed(self, connected):
        self.connected = connected
        if connected:
            await self.exchange(
                lambda: [self.engine.message("resource.config", self.engine.resource)]
            )
            await self.flush()
        self.notify()

    def notify(self):
        if not self.closed:
            async_dispatcher_send(self.hass, self.signal)

    async def exchange(self, produce):
        async with self.lock:
            if self.closed:
                return

            def work():
                outgoing = produce()
                if self.peer:
                    queue = [("ha", msg) for msg in outgoing]
                    count = 0
                    while queue:
                        side, msg = queue.pop(0)
                        count += 1
                        if count > 200:
                            raise RuntimeError("bounded_loop_exceeded")
                        responses = (
                            self.peer.receive(msg) if side == "ha" else self.engine.process(msg)
                        )
                        queue.extend(("cloud" if side == "ha" else "ha", r) for r in responses)
                    # Receipt words never wait for another receipt.
                return outgoing

            try:
                outgoing = await self.hass.async_add_executor_job(work)
                if self.transport:
                    for msg in outgoing:
                        self.transport.send(msg)
            except (ValueError, OSError, RuntimeError) as err:
                self.last_error = f"exchange_{type(err).__name__}"
        self.notify()

    async def incoming(self, body):
        try:
            msg = Message.model_validate(body)
        except ValueError:
            self.last_error = "invalid_or_unsupported_message"
            self.notify()
            return
        await self.exchange(lambda: self.engine.process(msg))
        if (
            msg.kind == "reassessment"
            and not msg.historical
            and self.engine.notices.get(msg.body().notice_id)
        ):
            notice = msg.body()
            persistent_notification.async_create(
                self.hass,
                notice.evidence,
                title="GridWorks reassessment (TEST)"
                if notice.test_scenario
                else "GridWorks reassessment requested",
                notification_id=f"{DOMAIN}_{notice.notice_id}",
            )

    async def flush(self):
        async with self.lock:
            if self.closed or not self.transport or not self.connected:
                return
            messages = await self.hass.async_add_executor_job(self.journal.pending)
            for msg in messages:
                if clock_ms() - msg.created_ms > 180000:
                    msg = msg.model_copy(update={"historical": True})
                self.transport.send(msg)

    async def snapshot(self, overrides=None):
        now = clock_ms()
        readings, by_kind = [], {}
        registry = er.async_get(self.hass)
        for binding in self.profile["bindings"]:
            entity_id = binding["entity_id"]
            if binding.get("registry_id"):
                item = registry.async_get(binding["registry_id"])
                if item:
                    entity_id = item.entity_id
            state = (
                overrides[entity_id]
                if overrides and entity_id in overrides
                else self.hass.states.get(entity_id)
            )
            value, stamp, quality = read_value(state, binding, now)
            reading = Reading(
                channel_id=binding["channel_id"],
                value=value,
                observed_ms=stamp,
                received_ms=now,
                quality=quality,
                timestamp_basis="ha_report_time",
            )
            readings.append(reading)
            by_kind.setdefault(binding["kind"], []).append((binding, reading))
        self.last_snapshot = readings

        def produce():
            result = [
                self.engine.message(
                    "observations", Observations(readings=readings, observation_set_id=str(uuid4()))
                )
            ]
            context = [
                r
                for b, r in sum(
                    [
                        items
                        for kind, items in by_kind.items()
                        if kind in KINDS[KINDS.index("outdoor_temperature") :]
                    ],
                    [],
                )
            ]
            result.append(
                self.engine.message(
                    "context", Observations(readings=context, observation_set_id=str(uuid4()))
                )
            )
            actual_mode = by_kind.get("current_mode", [])
            mode_reading = actual_mode[0][1] if actual_mode else None
            mode = (
                str(mode_reading.value)
                if mode_reading and mode_reading.quality == "reported"
                else None
            )
            if mode is not None:
                matching = next(
                    (
                        m["mode_id"]
                        for m in self.profile["modes"]
                        if mode == (m.get("state_value") or m["mode_id"])
                    ),
                    None,
                )
                mode = matching
            if mode != self.last_mode:
                self.mode_since = mode_reading.observed_ms if mode_reading else None
                self.last_mode = mode
            result.append(
                self.engine.message(
                    "mode.event",
                    ModeEvent(
                        mode_id=mode,
                        occurred_ms=mode_reading.observed_ms if mode_reading else None,
                        active_since_ms=self.mode_since,
                        evidence="observed" if mode is not None else "unknown",
                    ),
                )
            )
            for mode_id, current in list(self.engine.availability.items()):
                values = current.model_dump()
                for kind, field in (
                    ("mode_availability", "available"),
                    ("mode_not_before", "not_before_ms"),
                    ("mode_expected_return", "expected_return_ms"),
                    ("mode_min_power", "min_power_w"),
                    ("mode_max_power", "max_power_w"),
                ):
                    for binding, reading in by_kind.get(kind, []):
                        if binding.get("mode_id") == mode_id:
                            value = reading.value if reading.quality == "reported" else None
                            if field == "available":
                                value = value if isinstance(value, bool) else None
                            elif isinstance(value, bool) or isinstance(value, str):
                                value = None
                            if isinstance(value, (int, float)) and not isinstance(value, bool):
                                if field.endswith("_ms") and binding.get("unit") == "s":
                                    value = int(value * 1000)
                                if field.endswith("_w") and binding.get("unit") == "kW":
                                    value *= 1000
                            values[field] = value
                result.append(self.engine.update_availability(Availability.model_validate(values)))
            for service in self.engine.resource.services:
                values = {"service_id": service.service_id}
                for kind, field in (
                    ("service_request", "requested"),
                    ("service_activity", "active"),
                    ("service_delivery", "delivered"),
                    ("service_adequacy", "adequate"),
                ):
                    for binding, reading in by_kind.get(kind, []):
                        if binding.get("service_id") == service.service_id:
                            values[field] = (
                                reading.value
                                if (
                                    reading.quality == "reported"
                                    and isinstance(reading.value, bool)
                                )
                                else None
                            )
                            values["observed_ms"] = reading.observed_ms
                result.append(self.engine.message("service.status", ServiceStatus(**values)))
            dropped = self.journal.get("dropped", 0)
            if dropped > self.journal.get("gap_reported", 0):
                result.append(
                    self.engine.message(
                        "gap",
                        Gap(
                            dropped_count=dropped,
                            reason=self.journal.get("gap_reason", "bounded_outbox_overflow"),
                        ),
                    )
                )
                self.journal.set("gap_reported", dropped)
            return result

        await self.exchange(produce)

    async def tick(self):
        await self.snapshot()
        await self.exchange(lambda: [*self.engine.due_decision(), self.engine.heartbeat()])
        if self.peer:
            async with self.lock:
                messages = await self.hass.async_add_executor_job(
                    lambda: [self.peer.heartbeat(), *self.peer.propose(), *self.peer.pending()]
                )
            for message in messages:
                await self.incoming(message.model_dump(by_alias=True))
        await self.flush()

    async def system_changed(self):
        await self.exchange(
            lambda: [
                self.engine.system_changed(
                    [b["channel_id"] for b in self.profile["bindings"]],
                    "User requested reassessment",
                )
            ]
        )

    async def set_participation(self, status):
        await self.exchange(lambda: [self.engine.set_participation(status)])

    async def confirm_weather(self, primary, backups):
        def produce():
            proposal = self.engine.weather_proposal
            if proposal is None:
                raise ValueError("no weather proposal")
            return [
                self.engine.select_weather(
                    WeatherSelection(
                        proposal_id=proposal.proposal_id,
                        primary_source=primary,
                        backup_sources=backups,
                        confirmed=True,
                    )
                )
            ]

        await self.exchange(produce)

    async def acknowledge_notices(self):
        await self.exchange(
            lambda: [
                self.engine.acknowledge_notice(key)
                for key, value in self.engine.notices.items()
                if value["status"] not in ("acknowledged", "resolved")
            ]
        )

    async def run_scenarios(self):
        if not self.peer:
            self.last_error = "test_scenarios_require_local_demo_peer"
            self.notify()
            return
        async with self.lock:
            notice = await self.hass.async_add_executor_job(self.peer.reassessment_scenario)
            weather = await self.hass.async_add_executor_job(self.peer.weather_fallback_scenario)
        await self.incoming(notice.model_dump(by_alias=True))
        await self.incoming(weather.model_dump(by_alias=True))
        self.last_protocol_check = "reassessment_scenario_exercised_not_full_cloud_test"
        await self.tick()

    async def close(self):
        for unsubscribe in self.unsubscribers:
            unsubscribe()
        self.unsubscribers.clear()
        self.closed = True
        for task in list(self.tasks):
            task.cancel()
        await asyncio.gather(*list(self.tasks), return_exceptions=True)
        if self.transport:
            await self.hass.async_add_executor_job(self.transport.stop)
        async with self.lock:
            if self.journal:
                await self.hass.async_add_executor_job(self.journal.close)
            if self.peer_journal:
                await self.hass.async_add_executor_job(self.peer_journal.close)
