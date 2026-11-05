"""Portable alternative shadow policy. Alice is not imported or modified.

Runs embedded for demonstration or as the same broker-side CLI peer.
It does not optimize, predict plant response, or connect to live market actors.
"""

from __future__ import annotations

from uuid import uuid4

from .const import PREFIX
from .protocol import (
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
    def __init__(self, clock):
        self.clock = clock
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
        self.participation = "unknown"
        self.last_decision = None

    def make(self, kind, body):
        self.sequence += 1
        return Message(
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
        if msg.message_id in self.seen:
            return self.seen[msg.message_id]
        body = msg.body()
        self.last_peer_id = msg.message_id if not msg.historical else self.last_peer_id
        self.received[msg.kind] = msg.model_dump(by_alias=True)
        if msg.kind == "receipt":
            self.seen[msg.message_id] = []
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
            elif msg.kind == "availability":
                self.availability[body.mode_id] = body.available
            elif msg.kind == "participation":
                self.participation = body.status
            elif msg.kind == "weather.selection":
                self.weather = body.primary_source
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
