"""Dedicated MQTT client for the provisional shadow transport, independent of HA MQTT."""

from __future__ import annotations

import json
import ssl
from uuid import uuid4

import paho.mqtt.client as mqtt


class ShadowMqtt:
    """All callbacks marshalled to caller's loop. TLS mandatory outside loopback."""

    def __init__(self, config, on_message, on_connection):
        self.config = config
        self.on_message = on_message
        self.on_connection = on_connection
        self.connected = False
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=str(uuid4()),
            protocol=mqtt.MQTTv311,
            clean_session=True,
        )
        self.client.on_connect = self._connect
        self.client.on_subscribe = self._subscribe
        self.client.on_disconnect = self._disconnect
        self.client.on_message = self._message
        self.client.reconnect_delay_set(1, 60)
        self.client.max_queued_messages_set(1000)
        host = config["host"]
        local = host in ("localhost", "127.0.0.1", "::1")
        if not local or config.get("tls", True):
            self.client.tls_set(
                ca_certs=config.get("ca_path") or None,
                certfile=config.get("cert_path") or None,
                keyfile=config.get("key_path") or None,
                cert_reqs=ssl.CERT_REQUIRED,
                tls_version=ssl.PROTOCOL_TLS_CLIENT,
            )
        if config.get("username"):
            self.client.username_pw_set(config["username"])  # Approved certificate-CN profile only.
        self.receive_topic = config["receive_topic"]
        self.send_topic = config["send_topic"]
        if self.receive_topic == self.send_topic or any(
            token in topic
            for topic in (self.receive_topic, self.send_topic)
            for token in ("#", "+")
        ):
            raise ValueError("distinct exact shadow topics required")

    def start(self):
        self.client.connect_async(self.config["host"], int(self.config.get("port", 8883)), 60)
        self.client.loop_start()

    def _connect(self, client, userdata, flags, reason_code, properties):
        self.connected = False
        if reason_code.is_failure:
            self.on_connection(False)
            return
        _result, self._subscription_mid = client.subscribe(self.receive_topic, qos=1)

    def _subscribe(self, client, userdata, mid, reason_codes, properties):
        if mid != getattr(self, "_subscription_mid", None):
            return
        self.connected = bool(reason_codes) and not any(code.is_failure for code in reason_codes)
        self.on_connection(self.connected)

    def _disconnect(self, client, userdata, flags, reason_code, properties):
        self.connected = False
        self.on_connection(False)

    def _message(self, client, userdata, message):
        if message.topic != self.receive_topic or message.retain or len(message.payload) > 262144:
            return
        try:
            self.on_message(json.loads(message.payload))
        except ValueError, UnicodeError:
            return

    def send(self, message):
        if self.connected:
            self.client.publish(
                self.send_topic, message.model_dump_json(by_alias=True), qos=1, retain=False
            )

    def stop(self):
        self.client.disconnect()
        self.client.loop_stop()
