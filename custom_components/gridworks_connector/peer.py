"""Portable alternative shadow policy. Alice is not imported or modified.

Runs embedded for demonstration or as the same broker-side CLI peer.
It does not optimize, predict plant response, or connect to live market actors.
"""

from __future__ import annotations

from uuid import uuid4

from .const import PREFIX
from .protocol import (
    CalculatedContext,
    Heartbeat,
    Message,
    Receipt,
    Request,
    Reassessment,
    Resource,
    WeatherProposal,
    WeatherSource,
    WeatherStatus,
)


class ShadowPeer:
    def __init__(self, clock, journal=None):
        self.clock = clock
        self.journal = journal
        self.resource = None
        self.session = None
        self.resource_id = None
        self.revision = None
        self.sequence = 0
        self.request_sequence = 0
        self.current_request_id = None
        self.last_peer_id = None
        self.seen = {}
        self.availability = {}
        self.received = {}
        self.last_request_window = None
        self.proposal = None
        self.weather = None
        self.weather_backups = []
        self.participation = "unknown"
        self.last_decision = None

        if self.journal:
            saved = self.journal.get("cloud_state")
            if saved:
                for field in self.state_fields():
                    setattr(self, field, saved.get(field))
                self.resource = (
                    Resource.model_validate(saved["resource"]) if saved["resource"] else None
                )
                self.proposal = (
                    WeatherProposal.model_validate(saved["proposal"]) if saved["proposal"] else None
                )
                self.last_decision = None

    @staticmethod
    def state_fields():
        return (
            "session",
            "resource_id",
            "revision",
            "sequence",
            "request_sequence",
            "current_request_id",
            "last_peer_id",
            "availability",
            "received",
            "last_request_window",
            "weather",
            "weather_backups",
            "participation",
        )

    def save(self):
        if not self.journal:
            return
        state = {field: getattr(self, field) for field in self.state_fields()}
        state["resource"] = self.resource.model_dump() if self.resource else None
        state["proposal"] = self.proposal.model_dump() if self.proposal else None
        self.journal.set("cloud_state", state)

    def pending(self):
        if not self.journal:
            return []
        return [
            m.model_copy(update={"historical": True}) if self.clock() - m.created_ms > 180000 else m
            for m in self.journal.pending()
        ]

    def make(self, kind, body):
        self.sequence += 1
        message = Message(
            type_name=PREFIX + kind,
            resource_id=self.resource_id,
            session_id=self.session,
            sender="cloud",
            receiver="ha",
            created_ms=self.clock(),
            sequence=self.sequence,
            config_revision=self.revision,
            payload=body.model_dump(by_alias=True),
        )

        if self.journal:
            self.journal.enqueue(message)
            self.save()
        return message

    def receive(self, msg: Message):
        if msg.sender != "ha" or msg.receiver != "cloud":
            raise ValueError("wrong peer direction")
        if msg.kind == "resource.config" and not msg.historical:
            if self.session != msg.session_id or self.revision != msg.config_revision:
                self.seen.clear()
                self.current_request_id = None
                self.last_request_window = None
            self.resource_id, self.session, self.revision = (
                msg.resource_id,
                msg.session_id,
                msg.config_revision,
            )
            self.resource = Resource.model_validate(msg.payload)
            self.availability = {m.mode_id: m.declared_available for m in self.resource.modes}
        if (
            msg.session_id != self.session
            or msg.resource_id != self.resource_id
            or msg.config_revision != self.revision
        ):
            raise ValueError("resource not registered for this session/revision")
        if self.journal:
            cached = self.journal.cached(msg.message_id)
            if cached is not None:
                return cached
        if msg.message_id in self.seen:
            return self.seen[msg.message_id]
        body = msg.body()
        self.last_peer_id = msg.message_id if not msg.historical else self.last_peer_id
        self.received[msg.kind] = msg.model_dump(by_alias=True)
        if msg.kind == "receipt":
            if self.journal:
                self.journal.ack(body.message_id)
                self.journal.receive(msg, [])
            self.seen[msg.message_id] = []
            self.save()
            return []
        replies = [self.make("receipt", Receipt(message_id=msg.message_id, status="ingested"))]
        if not msg.historical:
            if msg.kind == "resource.config":
                self.proposal = WeatherProposal(
                    proposal_id=str(uuid4()),
                    sources=[
                        WeatherSource(
                            source_id="site",
                            label="Commissioned local observations",
                            coverage="Selected site sensors only",
                            variables=["temperature", "rain", "irradiance"],
                            provenance="test_catalog",
                        ),
                        WeatherSource(
                            source_id="remote-pending",
                            label="Remote source pending review",
                            coverage="Test catalog entry; not live weather",
                            variables=["temperature"],
                            provenance="test_catalog",
                        ),
                    ],
                )

                replies.append(self.make("weather.proposal", self.proposal))
                calculated = self.calculated_context()
                if calculated is not None:
                    replies.append(calculated)
            elif msg.kind == "availability":
                self.availability[body.mode_id] = body.available
            elif msg.kind == "participation":
                self.participation = body.status
            elif msg.kind == "weather.selection":
                self.weather = body.primary_source
                self.weather_backups = list(body.backup_sources)
                replies.append(
                    self.make(
                        "weather.status",
                        WeatherStatus(
                            source_id=self.weather, reason="test_catalog_selection_confirmed"
                        ),
                    )
                )
            elif msg.kind == "shadow.decision":
                self.last_decision = body
                # React exactly once to deliberate substitution, not an infinite echo loop.
                if body.deliberate_substitution and body.selected_mode:
                    replies.extend(self.propose(preferred_mode=body.selected_mode, force=True))
            elif msg.kind == "configuration.change":
                self.current_request_id = None
            elif msg.kind == "peer.status":
                self.participation = body.participation
                self.request_sequence = max(self.request_sequence, body.last_request_sequence)

        if self.journal:
            self.journal.receive(msg, replies)
        self.save()
        self.seen[msg.message_id] = replies
        if len(self.seen) > 2000:
            self.seen.pop(next(iter(self.seen)))
        return replies

    def heartbeat(self):
        return self.make(
            "peer.status",
            Heartbeat(
                current_request_id=self.current_request_id,
                participation=self.participation,
                last_peer_message_id=self.last_peer_id,
                ready=self.resource is not None,
                engine_healthy=True,
            ),
        )

    def propose(self, preferred_mode=None, force=False):
        if self.resource is None or self.participation == "paused":
            return []
        now = self.clock()
        window = now // 300000
        if not force and self.last_request_window == window:
            return []
        if not self.resource.meters:
            return []
        self.last_request_window = window
        self.request_sequence += 1
        self.current_request_id = str(uuid4())
        modes = list(self.availability)
        return [
            self.make(
                "shadow.request",
                Request(
                    request_id=self.current_request_id,
                    request_sequence=self.request_sequence,
                    valid_from_ms=now,
                    valid_until_ms=(window + 1) * 300000,
                    average_power_w=1000.0,
                    electrical_boundary=self.resource.meters[0].meter_id,
                    preferred_mode=preferred_mode or (modes[0] if modes else None),
                    intent="communications_test_only",
                ),
            )
        ]

    def reassessment_scenario(self):
        return self.make(
            "reassessment",
            Reassessment(
                notice_id=str(uuid4()),
                status="suspected",
                test_scenario=True,
                evidence="TEST: exercise reassessment delivery; no real system change inferred.",
            ),
        )

    def calculated_context(self):
        """Actual solar geometry from commissioned coordinates/time, not measured irradiance."""
        from datetime import datetime, timezone
        from astral import Observer
        from astral.sun import azimuth, zenith

        location = self.resource.location
        if "latitude" not in location or "longitude" not in location:
            return None
        observer = Observer(
            latitude=float(location["latitude"]), longitude=float(location["longitude"])
        )
        when = datetime.fromtimestamp(self.clock() / 1000, tz=timezone.utc)
        return self.make(
            "context.calculated",
            CalculatedContext(
                observed_ms=self.clock(),
                source="astral-2.2/site-coordinates",
                solar_azimuth_deg=azimuth(observer, when),
                solar_zenith_deg=zenith(observer, when),
            ),
        )

    def weather_fallback_scenario(self):
        return self.make(
            "weather.status",
            WeatherStatus(
                source_id=self.weather_backups[0] if self.weather_backups else None,
                test_scenario=True,
                reason="TEST: fallback message only; no provider outage was observed.",
            ),
        )
