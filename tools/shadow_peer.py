"""Run the alternative peer on an APPROVED TEST MQTT endpoint; no market code."""

import argparse
import json
import logging
import time

from custom_components.gridworks_connector.peer import ShadowPeer
from custom_components.gridworks_connector.protocol import Message
from custom_components.gridworks_connector.transport import ShadowMqtt

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--config", required=True, help="Protected local JSON; never commit it")
args = parser.parse_args()
with open(args.config, encoding="utf-8") as stream:
    config = json.load(stream)
if config.get("test_endpoint_confirmed") is not True:
    parser.error("test_endpoint_confirmed must be true")
peer = ShadowPeer(lambda: int(time.time() * 1000))
logging.basicConfig(level=logging.INFO)


def receive(body):
    try:
        for reply in peer.receive(Message.model_validate(body)):
            client.send(reply)
    except ValueError:
        logging.warning("Rejected invalid/resource-mismatched test message")


client = ShadowMqtt(config, receive, lambda connected: logging.info("Connected: %s", connected))
client.start()
try:
    while True:
        time.sleep(60)
        if peer.resource and client.connected:
            client.send(peer.heartbeat())
            for proposal in peer.propose():
                client.send(proposal)
except KeyboardInterrupt:
    client.stop()
