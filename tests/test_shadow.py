"""COM04/05/07/08/09/10/11/13/14/15: exercise actual endpoint behavior."""

from uuid import uuid4

from custom_components.gridworks_connector.const import PREFIX
from custom_components.gridworks_connector.peer import ShadowPeer
from custom_components.gridworks_connector.protocol import (
    Availability,
    Heartbeat,
    Message,
    ModeEvent,
    Request,
    WeatherSelection,
)


def request(e, now, seq=1, **overrides):
    data = dict(
        request_id=str(uuid4()),
        request_sequence=seq,
        valid_from_ms=now - 1000,
        valid_until_ms=now + 300000,
        average_power_w=6000,
        electrical_boundary="plant",
        preferred_mode="A",
    )
    data.update(overrides)
    return Request(**data)


def cloud(e, now, kind, payload, **overrides):
    return Message(
        type_name=PREFIX + kind,
        resource_id=e.resource_id,
        session_id=e.session_id,
        sender="cloud",
        receiver="ha",
        created_ms=now,
        sequence=1,
        config_revision=1,
        payload=payload.model_dump(by_alias=True),
        **overrides,
    )


def pump(e, peer, messages):
    queue = [("ha", m) for m in messages]
    count = 0
    while queue:
        side, msg = queue.pop(0)
        count += 1
        assert count < 200
        replies = peer.receive(msg) if side == "ha" else e.process(msg)
        queue.extend(("cloud" if side == "ha" else "ha", r) for r in replies)


def test_substitution_and_target_limit(endpoint):
    e, now, _ = endpoint
    e.update_availability(Availability(mode_id="B", available=True, max_power_w=2000))
    decision = e.evaluate(request(e, now[0]))
    assert decision.disposition == "would_pursue_with_changes"
    assert decision.selected_mode == "B" and decision.deliberate_substitution
    assert decision.target_status == "limited"


def test_cloud_consumes_substitution_and_changes_next_request(endpoint):
    e, now, _ = endpoint
    peer = ShadowPeer(lambda: now[0])
    pump(e, peer, [e.message("resource.config", e.resource)])
    proposals = peer.propose(preferred_mode="A", force=True)
    for p in proposals:
        replies = e.process(p)
        pump(e, peer, replies)
    assert peer.last_decision.selected_mode == "B"
    assert peer.last_decision.deliberate_substitution is False
    assert e.current_request.preferred_mode == "B"


def test_expired_and_partially_elapsed_and_future(endpoint):
    e, now, _ = endpoint
    assert e.evaluate(request(e, now[0], valid_until_ms=now[0])).disposition == "expired"
    future = request(e, now[0], seq=2, valid_from_ms=now[0] + 10000)
    assert e.evaluate(future).disposition == "future"
    now[0] += 10000
    due = e.due_decision()
    assert len(due) == 1 and due[0].body().disposition == "would_pursue_with_changes"
    assert e.due_decision() == []
    assert e.evaluate(request(e, now[0], seq=3)).partially_elapsed


def test_pause_and_unknown_electrical_boundary(endpoint):
    e, now, _ = endpoint
    e.set_participation("paused")
    assert e.evaluate(request(e, now[0])).disposition == "would_decline"
    e.set_participation("pursuing")
    assert (
        e.evaluate(request(e, now[0], seq=2, electrical_boundary="missing")).disposition
        == "cannot_assess"
    )


def test_not_before_is_not_availability_guarantee(endpoint):
    e, now, _ = endpoint
    e.update_availability(Availability(mode_id="B", available=True, not_before_ms=now[0] + 60000))
    assert e.evaluate(request(e, now[0])).disposition == "cannot_assess"


def test_duplicate_request_returns_same_decision(endpoint):
    e, now, journal = endpoint
    msg = cloud(e, now[0], "shadow.request", request(e, now[0]))
    first = e.process(msg)
    second = e.process(msg)
    assert [m.message_id for m in first] == [m.message_id for m in second]
    assert e.request_sequence == 1
    assert all(m.kind != "receipt" for m in journal.pending())


def test_historical_heartbeat_not_fresh_and_request_expired(endpoint):
    e, now, _ = endpoint
    msg = cloud(
        e, now[0], "peer.status", Heartbeat(participation="pursuing", ready=True), historical=True
    )
    e.process(msg)
    assert not e.peer_fresh
    replies = e.process(cloud(e, now[0], "shadow.request", request(e, now[0]), historical=True))
    assert replies[-1].body().disposition == "expired"


def test_weather_confirm_and_notice_acknowledgement(endpoint):
    e, now, _ = endpoint
    peer = ShadowPeer(lambda: now[0])
    pump(e, peer, [e.message("resource.config", e.resource)])
    proposal = e.weather_proposal
    pump(
        e,
        peer,
        [
            e.select_weather(
                WeatherSelection(
                    proposal_id=proposal.proposal_id,
                    primary_source="site",
                    backup_sources=["remote-pending"],
                    confirmed=True,
                )
            )
        ],
    )
    assert peer.weather == "site"
    assert e.weather_status.source_id == "site"
    notice = peer.reassessment_scenario()
    pump(e, peer, e.process(notice))
    pump(e, peer, [e.acknowledge_notice(notice.body().notice_id)])
    assert peer.received["reassessment"]["Payload"]["Status"] == "acknowledged"


def test_actual_mode_stays_separate_from_hypothetical(endpoint):
    e, now, _ = endpoint
    peer = ShadowPeer(lambda: now[0])
    pump(e, peer, [e.message("resource.config", e.resource)])
    pump(
        e,
        peer,
        [
            e.message(
                "mode.event",
                ModeEvent(
                    mode_id="A", occurred_ms=now[0], active_since_ms=now[0], evidence="observed"
                ),
            )
        ],
    )
    e.evaluate(request(e, now[0]))
    assert peer.received["mode.event"]["Payload"]["ModeId"] == "A"


def test_configuration_change_consumed(endpoint):
    e, now, _ = endpoint
    peer = ShadowPeer(lambda: now[0])
    pump(e, peer, [e.message("resource.config", e.resource)])
    pump(e, peer, [e.system_changed(["temperature-1"], "Sensor replaced")])
    assert peer.received["configuration.change"]["Payload"]["AffectedIds"] == ["temperature-1"]


def test_bad_revision_is_rejected(endpoint):
    e, now, _ = endpoint
    msg = cloud(e, now[0], "shadow.request", request(e, now[0]))
    msg = msg.model_copy(update={"config_revision": 2})
    assert e.process(msg)[0].body().status == "rejected"
    assert not e.peer_fresh


def test_restored_journal_has_no_fresh_contact(endpoint, resource):
    e, now, journal = endpoint
    msg = cloud(e, now[0], "shadow.request", request(e, now[0]))
    e.process(msg)
    from custom_components.gridworks_connector.engine import ShadowEngine

    restored = ShadowEngine(e.resource_id, 1, resource, journal, lambda: now[0])
    assert not restored.peer_fresh
    assert len(restored.process(msg)) == 2
