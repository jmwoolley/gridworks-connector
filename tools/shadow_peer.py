"""Run the alternative peer on an APPROVED TEST MQTT endpoint; no market code."""

import argparse
import json
import logging
from pathlib import Path
from queue import Empty, Full, Queue
import time

from custom_components.gridworks_connector.journal import Journal
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
journal = Journal(config.get("database_path") or str(Path(args.config).with_suffix(".sqlite")))
peer = ShadowPeer(lambda: int(time.time() * 1000), journal)
inbound = Queue(maxsize=1000)
logging.basicConfig(level=logging.INFO)


def receive(body):
    try:
        inbound.put_nowait(body)
    except Full:
        logging.warning("Bounded incoming queue full; sender must retry pending messages")


client = ShadowMqtt(config, receive, lambda connected: logging.info("Connected: %s", connected))
client.start()
next_tick = time.monotonic() + 60
try:
    while True:
        try:
            body = inbound.get(timeout=0.5)
        except Empty:
            body = None
        if body is not None:
            try:
                for reply in peer.receive(Message.model_validate(body)):
                    client.send(reply)
            except ValueError:
                logging.warning("Rejected invalid/resource-mismatched test message")
        if time.monotonic() >= next_tick:
            if peer.resource and client.connected:
                messages = [peer.heartbeat(), *peer.propose(), *peer.pending()]
                for message in {m.message_id: m for m in messages}.values():
                    client.send(message)
            next_tick = time.monotonic() + 60
except KeyboardInterrupt:
    pass
finally:
    client.stop()
    journal.close()
