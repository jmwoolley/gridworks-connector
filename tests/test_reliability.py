"""Regression tests for bounded queues, restarted peers and config revisions."""

from custom_components.gridworks_connector.engine import ShadowEngine
from custom_components.gridworks_connector.journal import Journal
from custom_components.gridworks_connector.peer import ShadowPeer
from custom_components.gridworks_connector.protocol import Observations


def test_bounded_outbox_reports_loss(endpoint, monkeypatch):
    e, _, journal = endpoint
    import custom_components.gridworks_connector.journal as module

    monkeypatch.setattr(module, "MAX_OUTBOX", 3)
    for index in range(5):
        e.message("observations", Observations(observation_set_id=str(index), readings=[]))
    assert len(journal.pending()) == 3
    assert journal.get("dropped") == 2


def test_revision_retires_unacknowledged_old_session(endpoint, resource):
    e, now, journal = endpoint
    e.message("resource.config", resource)
    old_session = e.session_id
    newer = ShadowEngine(e.resource_id, 2, resource, journal, lambda: now[0])
    assert newer.session_id != old_session
    assert journal.get("dropped") == 1
    assert not journal.pending()
    assert newer.request_sequence == 0


def test_peer_restarts_with_durable_reply_and_request_counter(endpoint, tmp_path):
    e, now, _ = endpoint
    journal = Journal(str(tmp_path / "peer.sqlite"))
    try:
        peer = ShadowPeer(lambda: now[0], journal)
        config = e.message("resource.config", e.resource)
        replies = peer.receive(config)
        peer.request_sequence = 22
        peer.save()
        restored = ShadowPeer(lambda: now[0], journal)
        assert restored.request_sequence == 22
        assert [m.message_id for m in restored.receive(config)] == [m.message_id for m in replies]
        assert restored.resource.name == e.resource.name
    finally:
        journal.close()


def test_calculated_solar_has_explicit_source(endpoint):
    e, now, _ = endpoint
    resource = e.resource.model_copy(update={"location": {"latitude": 42.0, "longitude": -72.0}})
    peer = ShadowPeer(lambda: now[0])
    replies = peer.receive(e.message("resource.config", resource))
    calculated = next(m.body() for m in replies if m.kind == "context.calculated")
    assert 0 <= calculated.solar_azimuth_deg <= 360
    assert 0 <= calculated.solar_zenith_deg <= 180
    assert calculated.source.startswith("astral")


def test_peer_recovers_counter_from_ha_heartbeat(endpoint):
    e, now, _ = endpoint
    peer = ShadowPeer(lambda: now[0])
    peer.receive(e.message("resource.config", e.resource))
    e.request_sequence = 37
    peer.receive(e.heartbeat())
    assert peer.propose(force=True)[0].body().request_sequence == 38


def test_unselected_context_is_not_exported_in_registration(endpoint):
    e, _, _ = endpoint
    word = e.message("resource.config", e.resource)
    assert "entity_id" not in word.model_dump_json()
    assert "registry_id" not in word.model_dump_json()


def test_every_generated_schema_validates_its_resource_example(endpoint):
    import json
    from pathlib import Path
    import jsonschema

    e, _, _ = endpoint
    root = Path(__file__).resolve().parents[1]
    schema = json.loads(
        (root / "docs/proposed-sema/gw.thermal.resource.config.000.schema.json").read_text()
    )
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(e.message("resource.config", e.resource).model_dump(by_alias=True), schema)
