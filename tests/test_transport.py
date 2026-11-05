"""Transport boundaries: exact topics, retained-request refusal and TLS validation."""

import json
import ssl
from types import SimpleNamespace

import pytest

from custom_components.gridworks_connector.transport import ShadowMqtt


def config(**values):
    return {
        "host": "127.0.0.1",
        "port": 1885,
        "tls": False,
        "send_topic": "shadow/test/ha",
        "receive_topic": "shadow/test/cloud",
        **values,
    }


def test_wildcard_or_same_topics_refused():
    for value in ("shadow/#", "shadow/+", "shadow/test/ha"):
        with pytest.raises(ValueError):
            ShadowMqtt(config(receive_topic=value), lambda body: None, lambda status: None)


def test_retained_wrong_topic_and_oversized_messages_are_discarded():
    received = []
    transport = ShadowMqtt(config(), received.append, lambda status: None)
    for message in (
        SimpleNamespace(topic="shadow/test/cloud", retain=True, payload=b"{}"),
        SimpleNamespace(topic="other", retain=False, payload=b"{}"),
        SimpleNamespace(topic="shadow/test/cloud", retain=False, payload=b"x" * 262145),
    ):
        transport._message(None, None, message)
    assert not received
    transport._message(
        None,
        None,
        SimpleNamespace(
            topic="shadow/test/cloud", retain=False, payload=json.dumps({"valid": True}).encode()
        ),
    )
    assert received == [{"valid": True}]


def test_nonloopback_never_turns_off_tls(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "paho.mqtt.client.Client.tls_set", lambda self, **kwargs: calls.append(kwargs)
    )
    ShadowMqtt(config(host="test.invalid", tls=False), lambda body: None, lambda status: None)
    assert calls[0]["cert_reqs"] == ssl.CERT_REQUIRED
    assert calls[0]["tls_version"] == ssl.PROTOCOL_TLS_CLIENT
