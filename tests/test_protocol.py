"""COM01/02/03/06/12/16: reject ambiguous identity, missing limits and malformed wire."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from custom_components.gridworks_connector.const import PREFIX
from custom_components.gridworks_connector.protocol import (
    Bounds,
    Channel,
    Message,
    Observations,
    Reading,
    Request,
    Resource,
    ServiceStatus,
)


def test_fingerprint_limits_required():
    with pytest.raises(ValidationError):
        Channel(channel_id="x", kind="temperature")
    with pytest.raises(ValidationError):
        Bounds(lower=90, upper=10)


def test_electrical_channel_needs_meter(resource):
    data = resource.model_dump()
    data["channels"].append({"channel_id": "power", "kind": "power", "unit": "W"})
    with pytest.raises(ValidationError):
        Resource.model_validate(data)


def test_identity_and_domain_are_strict(endpoint):
    e, _, _ = endpoint
    message = e.message("resource.config", e.resource).model_dump(by_alias=True)
    message["Shadow"] = False
    with pytest.raises(ValidationError):
        Message.model_validate(message)
    message["Shadow"] = True
    message["TypeName"] = "arbitrary.command"
    with pytest.raises(ValidationError):
        Message.model_validate(message)


def test_no_single_timestamp_for_batch(endpoint):
    e, _, _ = endpoint
    msg = e.message(
        "observations",
        Observations(
            observation_set_id="set",
            readings=[
                Reading(
                    channel_id="t1",
                    value=30.0,
                    observed_ms=100,
                    received_ms=150,
                    quality="reported",
                    timestamp_basis="ha_report_time",
                ),
                Reading(
                    channel_id="t2",
                    value=None,
                    observed_ms=90,
                    received_ms=150,
                    quality="unavailable",
                    timestamp_basis="ha_report_time",
                ),
            ],
        ),
    )
    copy = Message.model_validate_json(msg.model_dump_json(by_alias=True))
    assert [r.observed_ms for r in copy.body().readings] == [100, 90]
    assert copy.body().readings[1].value is None


def test_open_loop_delivery_is_unknown():
    status = ServiceStatus(service_id="heating", requested=True)
    assert status.delivered is None
    assert status.adequate is None


def test_invalid_numbers_and_windows():
    with pytest.raises(ValidationError):
        Bounds(lower=float("nan"), upper=90)
    with pytest.raises(ValidationError):
        Request(
            request_id=str(uuid4()),
            request_sequence=1,
            valid_from_ms=5,
            valid_until_ms=4,
            average_power_w=1000,
            electrical_boundary="plant",
        )


def test_wrong_peer_never_becomes_fresh(endpoint):
    e, _, _ = endpoint
    bad = Message(
        type_name=PREFIX + "receipt",
        resource_id=e.resource_id,
        session_id=e.session_id,
        sender="stranger",
        receiver="ha",
        created_ms=1000000,
        sequence=1,
        config_revision=1,
        payload={"MessageId": str(uuid4()), "Status": "ingested"},
    )
    with pytest.raises(ValueError):
        e.process(bad)
    assert not e.peer_fresh
