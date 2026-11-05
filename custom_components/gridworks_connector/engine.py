"""Portable non-actuating endpoint; contains no equipment service/call interface."""

from __future__ import annotations

from uuid import uuid4

from .const import PREFIX, PEER_STALE_SECONDS
from .protocol import (
    Availability,
    Change,
    Decision,
    Error,
    Heartbeat,
    Message,
    Participation,
    Receipt,
    Reassessment,
    Request,
    Resource,
    WeatherSelection,
)


class ShadowEngine:
    def __init__(
        self,
        resource_id,
        config_revision,
        resource: Resource,
        journal,
        clock,
        sender="ha",
        receiver="cloud",
    ):
        self.resource_id = resource_id
        self.revision = config_revision
        self.resource = resource
        self.journal = journal
        self.clock = clock
        self.sender, self.receiver = sender, receiver
        changed = journal.get("config_revision") != config_revision
        self.session_id = str(uuid4()) if changed else journal.get("session", str(uuid4()))
        journal.set("session", self.session_id)
        journal.set("config_revision", config_revision)
        if changed:
            journal.set("request_sequence", 0)
        journal.archive_other_sessions(self.session_id, config_revision)
        self.sequence = journal.get("sequence", 0)
        self.participation = journal.get("participation", "pursuing")
        self.current_request = None
        self.pending_request = None
        self.observations = {}
        self.request_sequence = journal.get("request_sequence", 0)
        self.last_peer_id = None
        self.last_peer_ms = None  # A restored heartbeat never proves fresh contact.
        self.peer_ready = False
        self.availability = {
            mode.mode_id: Availability(mode_id=mode.mode_id, available=mode.declared_available)
            for mode in resource.modes
        }
        self.weather_proposal = None
        self.weather_selection = journal.get("weather_selection")
        self.weather_status = None
        self.calculated_context = None
        self.notices = journal.get("notices", {})
        self.last_decision = None
        self.last_error = None

    def message(self, kind, payload):
        if kind == "observations":
            self.observations = {reading.channel_id: reading for reading in payload.readings}
        self.sequence += 1
        self.journal.set("sequence", self.sequence)
        msg = Message(
            type_name=PREFIX + kind,
            resource_id=self.resource_id,
            session_id=self.session_id,
            sender=self.sender,
            receiver=self.receiver,
            created_ms=self.clock(),
            sequence=self.sequence,
            config_revision=self.revision,
            payload=payload.model_dump(by_alias=True)
            if hasattr(payload, "model_dump")
            else payload,
        )
        self.journal.enqueue(msg)
        return msg

    def receipt(self, msg, status="ingested", detail=None):
        return self.message(
            "receipt", Receipt(message_id=msg.message_id, status=status, detail=detail)
        )

    def heartbeat(self):
        active = self.current_request
        if active and self.clock() >= active.valid_until_ms:
            self.current_request = None
        return self.message(
            "peer.status",
            Heartbeat(
                current_request_id=self.current_request.request_id
                if self.current_request
                else None,
                participation=self.participation,
                last_peer_message_id=self.last_peer_id,
                last_request_sequence=self.request_sequence,
                ready=self.peer_ready,
                engine_healthy=True,
            ),
        )

    @property
    def peer_fresh(self):
        return self.last_peer_ms is not None and (
            0 <= self.clock() - self.last_peer_ms <= PEER_STALE_SECONDS * 1000
        )

    def process(self, msg: Message):
        if (
            msg.resource_id != self.resource_id
            or msg.session_id != self.session_id
            or msg.sender != self.receiver
            or msg.receiver != self.sender
        ):
            raise ValueError("resource/session/peer mismatch")
        cached = self.journal.cached(msg.message_id)
        if cached is not None:
            return cached
        if msg.config_revision != self.revision:
            replies = [self.receipt(msg, "rejected", "configuration_revision_mismatch")]
            self.journal.receive(msg, replies)
            return replies
        if not msg.historical and abs(self.clock() - msg.created_ms) <= PEER_STALE_SECONDS * 1000:
            self.last_peer_ms = self.clock()
            self.last_peer_id = msg.message_id
        kind, body = msg.kind, msg.body()
        if kind == "receipt":
            if body.status in ("ingested", "duplicate"):
                self.journal.ack(body.message_id)
            self.journal.receive(msg, [])
            return []
        replies = [self.receipt(msg)]
        if msg.historical:
            # Historical requests and heartbeats may be stored but cannot renew authority.
            if kind == "shadow.request":
                replies.append(
                    self.message(
                        "shadow.decision",
                        Decision(
                            request_id=body.request_id,
                            disposition="expired",
                            reason="historical_replay",
                            preferred_mode=body.preferred_mode,
                        ),
                    )
                )
        elif kind == "shadow.request":
            self.last_decision = self.evaluate(body)
            replies.append(self.message("shadow.decision", self.last_decision))
        elif kind == "peer.status":
            self.peer_ready = body.ready and body.engine_healthy
            expected = self.current_request.request_id if self.current_request else None
            if body.current_request_id != expected:
                self.last_error = "peer_current_request_disagreement"
        elif kind == "weather.proposal":
            self.weather_proposal = body
        elif kind == "context.calculated":
            self.calculated_context = body
        elif kind == "weather.status":
            self.weather_status = body
        elif kind == "reassessment":
            self.notices[body.notice_id] = body.model_dump()
            self.notices = dict(list(self.notices.items())[-50:])
            self.journal.set("notices", self.notices)
        elif kind == "error":
            self.last_error = body.code
        else:
            replies.append(
                self.message(
                    "error",
                    Error(
                        code="unexpected_direction", detail=kind, related_message_id=msg.message_id
                    ),
                )
            )
        self.journal.receive(msg, replies)
        return replies

    def evaluate(self, request: Request, scheduled=False):
        kwargs = dict(
            request_id=request.request_id,
            preferred_mode=request.preferred_mode,
            partially_elapsed=self.clock() > request.valid_from_ms,
        )
        if not scheduled and request.request_sequence <= self.request_sequence:
            return Decision(disposition="superseded", reason="old_request_sequence", **kwargs)
        self.request_sequence = request.request_sequence
        self.journal.set("request_sequence", self.request_sequence)
        if self.clock() >= request.valid_until_ms:
            return Decision(disposition="expired", reason="window_ended", **kwargs)
        if self.clock() < request.valid_from_ms:
            self.pending_request = request
            return Decision(disposition="future", reason="not_started_no_action", **kwargs)
        self.pending_request = None
        self.current_request = request
        if self.participation == "paused":
            return Decision(disposition="would_decline", reason="local_pause", **kwargs)
        meters = {meter.meter_id for meter in self.resource.meters}
        if request.electrical_boundary not in meters:
            return Decision(
                disposition="cannot_assess", reason="uncommissioned_meter_boundary", **kwargs
            )
        candidates = [
            a
            for a in self.availability.values()
            if a.available is True and (a.not_before_ms is None or a.not_before_ms <= self.clock())
        ]
        selected = next((a for a in candidates if a.mode_id == request.preferred_mode), None)
        if selected is None and candidates:
            selected = candidates[0]
        if selected is None:
            return Decision(disposition="cannot_assess", reason="no_known_available_mode", **kwargs)
        changed = selected.mode_id != request.preferred_mode and request.preferred_mode is not None
        limited = (
            selected.min_power_w is not None and request.average_power_w < selected.min_power_w
        ) or (selected.max_power_w is not None and request.average_power_w > selected.max_power_w)
        return Decision(
            disposition="would_pursue_with_changes" if changed or limited else "would_pursue",
            selected_mode=selected.mode_id,
            deliberate_substitution=changed,
            target_status="limited" if limited else "pursuing",
            reason="declared_constraints_only_not_performance_prediction",
            **kwargs,
        )

    def due_decision(self):
        request = self.pending_request
        if request is None or self.clock() < request.valid_from_ms:
            return []
        self.pending_request = None
        self.last_decision = self.evaluate(request, scheduled=True)
        return [self.message("shadow.decision", self.last_decision)]

    def update_availability(self, item: Availability):
        if item.mode_id not in self.availability:
            raise ValueError("unknown mode")
        self.availability[item.mode_id] = item
        return self.message("availability", item)

    def set_participation(self, status):
        payload = Participation(
            status=status,
            request_id=self.current_request.request_id if self.current_request else None,
        )
        self.participation = status
        self.journal.set("participation", status)
        return self.message("participation", payload)

    def select_weather(self, selection: WeatherSelection):
        if not self.weather_proposal or selection.proposal_id != self.weather_proposal.proposal_id:
            raise ValueError("weather proposal not current")
        options = {source.source_id for source in self.weather_proposal.sources}
        selected = [selection.primary_source, *selection.backup_sources]
        if not selection.confirmed or any(s not in options for s in selected):
            raise ValueError("confirm proposed sources")
        if len(set(selected)) != len(selected):
            raise ValueError("weather sources must be distinct")
        self.weather_selection = selection.model_dump()
        self.journal.set("weather_selection", self.weather_selection)
        return self.message("weather.selection", selection)

    def system_changed(self, affected_ids, details=None):
        return self.message(
            "configuration.change",
            Change(
                revision=self.revision,
                effective_ms=self.clock(),
                affected_ids=affected_ids,
                details=details,
            ),
        )

    def acknowledge_notice(self, notice_id):
        if notice_id not in self.notices:
            raise ValueError("unknown reassessment notice")
        notice = Reassessment.model_validate(self.notices[notice_id])
        notice.status = "acknowledged"
        self.notices[notice_id] = notice.model_dump()
        self.journal.set("notices", self.notices)
        return self.message("reassessment", notice)
