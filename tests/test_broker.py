"""Real RabbitMQ MQTT seam in CI; not production GridWorks/FIS/Sema validation."""

import os
from queue import Empty, Queue
from threading import Event
import time

import pytest

from custom_components.gridworks_connector.peer import ShadowPeer
from custom_components.gridworks_connector.protocol import Message, Observations
from custom_components.gridworks_connector.transport import ShadowMqtt

pytestmark = [
    pytest.mark.skipif(
        os.environ.get("CONNECTOR_TEST_BROKER") != "1",
        reason="approved ephemeral CI development broker only",
    ),
    pytest.mark.usefixtures("socket_enabled"),
]


def test_shadow_round_trip_over_rabbitmq_mqtt(endpoint):
    engine, now, _ = endpoint
    peer = ShadowPeer(lambda: now[0])
    inbox = Queue()
    ready_ha, ready_cloud = Event(), Event()
    base = f"connector-test/{engine.resource_id}"
    config = {
        "host": "127.0.0.1",
        "port": 1885,
        "tls": False,
        "send_topic": base + "/ha",
        "receive_topic": base + "/cloud",
    }
    ha = ShadowMqtt(
        config,
        lambda body: inbox.put(("ha", body)),
        lambda connected: ready_ha.set() if connected else ready_ha.clear(),
    )
    cloud = ShadowMqtt(
        {**config, "send_topic": base + "/cloud", "receive_topic": base + "/ha"},
        lambda body: inbox.put(("cloud", body)),
        lambda connected: ready_cloud.set() if connected else ready_cloud.clear(),
    )
    # Ephemeral broker fixture only. Real GridWorks profile uses approved client certificates.
    for client in (ha, cloud):
        client.client.username_pw_set("connector_test", "ephemeral_ci_only")

    def drain_until(predicate):
        deadline = time.monotonic() + 15
        while not predicate():
            assert time.monotonic() < deadline, "broker round trip timed out"
            try:
                destination, body = inbox.get(timeout=0.2)
            except Empty:
                continue
            word = Message.model_validate(body)
            replies = engine.process(word) if destination == "ha" else peer.receive(word)
            for reply in replies:
                (ha if destination == "ha" else cloud).send(reply)

    try:
        cloud.start()
        ha.start()
        assert ready_ha.wait(15) and ready_cloud.wait(15)
        ha.send(engine.message("resource.config", engine.resource))
        drain_until(lambda: engine.weather_proposal is not None)
        for request in peer.propose(preferred_mode="A", force=True):
            cloud.send(request)
        drain_until(
            lambda: (
                peer.last_decision is not None
                and peer.last_decision.selected_mode == "B"
                and not peer.last_decision.deliberate_substitution
            )
        )
        assert engine.current_request.preferred_mode == "B"
        assert engine.peer_fresh
        # A deliberately disconnected endpoint retains application data until receipt.
        ha.stop()
        buffered = engine.message(
            "observations",
            Observations(observation_set_id="buffered-during-disconnect", readings=[]),
        )
        ha.send(buffered)
        assert any(m.message_id == buffered.message_id for m in engine.journal.pending())
        ha.start()
        assert ready_ha.wait(15)
        for pending in engine.journal.pending():
            ha.send(pending)
        drain_until(
            lambda: (
                peer.received.get("observations", {}).get("Payload", {}).get("ObservationSetId")
                == "buffered-during-disconnect"
                and not any(m.message_id == buffered.message_id for m in engine.journal.pending())
            )
        )
    finally:
        ha.stop()
        cloud.stop()
