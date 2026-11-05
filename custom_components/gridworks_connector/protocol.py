"""Proposed Sema-style vocabulary, NOT registry-published generated Sema.

PascalCase wire properties, dotted TypeName, literal Version and closed objects.
schemas/ is deterministically generated from these provisional local models.
"""

from __future__ import annotations

import json
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_pascal

from .const import PREFIX, PROTOCOL_REVISION


class Word(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_pascal,
        populate_by_name=True,
        extra="forbid",
        allow_inf_nan=False,
    )


class Bounds(Word):
    lower: float
    upper: float

    @model_validator(mode="after")
    def ordered(self):
        if self.lower >= self.upper:
            raise ValueError("lower must be less than upper")
        return self


class Channel(Word):
    channel_id: str = Field(min_length=1, max_length=128)
    kind: str
    unit: str | None = None
    limits: Bounds | None = None
    mode_id: str | None = None
    service_id: str | None = None
    meter_id: str | None = None
    timestamp_basis: str = "ha_report_time"

    @model_validator(mode="after")
    def temperature_limits(self):
        if self.kind == "temperature" and self.limits is None:
            raise ValueError("every fingerprint temperature requires commissioned limits")
        return self

    @model_validator(mode="after")
    def known_kind(self):
        from .const import KINDS

        if self.kind not in KINDS:
            raise ValueError("unknown channel kind")
        return self


class Mode(Word):
    mode_id: str = Field(min_length=1, max_length=128)
    label: str = Field(min_length=1, max_length=128)
    declared_available: bool | None = None


class Meter(Word):
    meter_id: str
    label: str
    coverage: str
    parent_meter_id: str | None = None
    authoritative: bool = False
    provenance: str | None = None


class Service(Word):
    service_id: str
    label: str
    kind: Literal["heating", "cooling", "dhw", "other"]
    delivery_feedback: bool = False


class Resource(Word):
    name: str
    channels: list[Channel]
    modes: list[Mode] = Field(default_factory=list)
    meters: list[Meter] = Field(default_factory=list)
    services: list[Service] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    location: dict[str, str | float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def unique_ids(self):
        for values, attr in (
            (self.channels, "channel_id"),
            (self.modes, "mode_id"),
            (self.meters, "meter_id"),
            (self.services, "service_id"),
        ):
            ids = [getattr(item, attr) for item in values]
            if len(ids) != len(set(ids)):
                raise ValueError(f"duplicate {attr}")
        if not self.channels or not any(c.kind == "temperature" for c in self.channels):
            raise ValueError("select at least one fingerprint temperature")
        modes = {m.mode_id for m in self.modes}
        meters = {m.meter_id for m in self.meters}
        services = {s.service_id for s in self.services}
        for channel in self.channels:
            if channel.kind in ("power", "energy") and not channel.meter_id:
                raise ValueError("electrical channel requires its meter boundary")
            if channel.kind.startswith("mode_") and not channel.mode_id:
                raise ValueError("mode capability channel requires a mode identity")
            if channel.kind.startswith("service_") and not channel.service_id:
                raise ValueError("service evidence requires a service identity")
            for value, valid in (
                (channel.mode_id, modes),
                (channel.meter_id, meters),
                (channel.service_id, services),
            ):
                if value is not None and value not in valid:
                    raise ValueError("channel references an unconfigured identity")
        return self


class Reading(Word):
    channel_id: str
    value: float | bool | str | None
    observed_ms: int | None = Field(default=None, ge=0)
    received_ms: int = Field(ge=0)
    quality: Literal["reported", "unknown", "unavailable", "invalid", "stale"]
    timestamp_basis: str


class Observations(Word):
    readings: list[Reading]
    observation_set_id: str
    gap: str | None = None


class Availability(Word):
    mode_id: str
    available: bool | None = None
    not_before_ms: int | None = None
    expected_return_ms: int | None = None
    min_power_w: float | None = None
    max_power_w: float | None = None


class ModeEvent(Word):
    mode_id: str | None
    occurred_ms: int | None
    active_since_ms: int | None
    evidence: Literal["observed", "unknown"]


class ServiceStatus(Word):
    service_id: str
    requested: bool | None = None
    active: bool | None = None
    delivered: bool | None = None
    adequate: bool | None = None
    observed_ms: int | None = None


class Participation(Word):
    status: Literal["pursuing", "modified", "paused", "unknown"]
    reason: str | None = Field(default=None, max_length=500)
    request_id: str | None = None


class Request(Word):
    request_id: str
    request_sequence: int = Field(ge=1)
    valid_from_ms: int = Field(ge=0)
    valid_until_ms: int = Field(ge=0)
    average_power_w: float = Field(ge=0, le=1000000)
    electrical_boundary: str
    preferred_mode: str | None = None
    intent: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def valid_window(self):
        if self.valid_until_ms <= self.valid_from_ms:
            raise ValueError("request end must follow start")
        return self


class Decision(Word):
    request_id: str
    disposition: Literal[
        "would_pursue",
        "would_pursue_with_changes",
        "would_decline",
        "cannot_assess",
        "expired",
        "future",
        "superseded",
    ]
    preferred_mode: str | None = None
    selected_mode: str | None = None
    deliberate_substitution: bool = False
    target_status: Literal["pursuing", "limited", "overridden", "unknown"] = "unknown"
    reason: str | None = Field(default=None, max_length=500)
    partially_elapsed: bool = False
    not_before_ms: int | None = None


class Heartbeat(Word):
    last_request_sequence: int = Field(default=0, ge=0)
    current_request_id: str | None = None
    participation: Literal["pursuing", "modified", "paused", "unknown"]
    last_peer_message_id: str | None = None
    ready: bool
    engine_healthy: bool = True


class Receipt(Word):
    message_id: str
    status: Literal["ingested", "rejected", "duplicate"]
    detail: str | None = Field(default=None, max_length=500)


class WeatherSource(Word):
    source_id: str
    label: str
    coverage: str
    variables: list[str]
    provenance: Literal["test_catalog", "provider_catalog", "commissioner"]


class WeatherProposal(Word):
    proposal_id: str
    sources: list[WeatherSource]


class WeatherSelection(Word):
    proposal_id: str
    primary_source: str
    backup_sources: list[str] = Field(default_factory=list)
    confirmed: bool


class CalculatedContext(Word):
    observed_ms: int
    source: str
    solar_azimuth_deg: float
    solar_zenith_deg: float


class WeatherStatus(Word):
    test_scenario: bool = False
    source_id: str | None
    reason: str | None = None
    issued_ms: int | None = None
    valid_ms: int | None = None


class Change(Word):
    revision: int = Field(ge=1)
    effective_ms: int
    affected_ids: list[str]
    details: str | None = Field(default=None, max_length=500)


class Reassessment(Word):
    notice_id: str
    status: Literal["suspected", "requested", "acknowledged", "resolved"]
    evidence: str = Field(max_length=1000)
    test_scenario: bool = False


class Gap(Word):
    dropped_count: int = Field(ge=1)
    reason: str


class Error(Word):
    code: str
    detail: str = Field(max_length=500)
    related_message_id: str | None = None


PAYLOADS = {
    "resource.config": Resource,
    "observations": Observations,
    "context": Observations,
    "context.calculated": CalculatedContext,
    "mode.event": ModeEvent,
    "availability": Availability,
    "service.status": ServiceStatus,
    "participation": Participation,
    "shadow.request": Request,
    "shadow.decision": Decision,
    "peer.status": Heartbeat,
    "receipt": Receipt,
    "weather.proposal": WeatherProposal,
    "weather.selection": WeatherSelection,
    "weather.status": WeatherStatus,
    "configuration.change": Change,
    "reassessment": Reassessment,
    "gap": Gap,
    "error": Error,
}


class Message(Word):
    type_name: str
    version: Literal["000"] = "000"
    protocol_revision: Literal["draft-2026-11-05"] = PROTOCOL_REVISION
    message_id: str = Field(default_factory=lambda: str(uuid4()))
    resource_id: str
    session_id: str
    sender: str
    receiver: str
    created_ms: int = Field(ge=0)
    sequence: int = Field(ge=1)
    config_revision: int = Field(ge=1)
    shadow: Literal[True] = True
    historical: bool = False
    payload: dict[str, Any]

    @model_validator(mode="after")
    def validate_word(self):
        for identity in (self.message_id, self.resource_id, self.session_id):
            UUID(identity)
        if not self.type_name.startswith(PREFIX):
            raise ValueError("not a thermal shadow word")
        model = PAYLOADS.get(self.type_name[len(PREFIX) :])
        if model is None:
            raise ValueError("unsupported TypeName")
        self.payload = model.model_validate(self.payload).model_dump(by_alias=True)
        # Also reject NaN/Infinity and non-JSON values anywhere.
        json.dumps(self.payload, allow_nan=False)
        return self

    @property
    def kind(self) -> str:
        return self.type_name[len(PREFIX) :]

    def body(self):
        return PAYLOADS[self.kind].model_validate(self.payload)
