"""Bounded SQLite journal/outbox; callers execute on a dedicated worker/lock."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .const import MAX_OUTBOX, MAX_TRACE
from .protocol import Message


class Journal:
    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS outbox (
            id TEXT PRIMARY KEY, sequence INTEGER, body TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS seen (
            id TEXT PRIMARY KEY, sequence INTEGER, replies TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS trace (
            ordinal INTEGER PRIMARY KEY AUTOINCREMENT, direction TEXT, body TEXT);
        """)
        self.db.commit()

    def get(self, key, default=None):
        row = self.db.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set(self, key, value):
        self.db.execute(
            "INSERT OR REPLACE INTO state VALUES (?,?)", (key, json.dumps(value, allow_nan=False))
        )
        self.db.commit()

    def enqueue(self, message: Message):
        body = message.model_dump_json(by_alias=True)
        with self.db:
            if message.kind != "receipt":
                self.db.execute(
                    "INSERT OR IGNORE INTO outbox VALUES (?,?,?)",
                    (message.message_id, message.sequence, body),
                )
            self._trace("out", body)
            rows = self.db.execute(
                "SELECT id FROM outbox ORDER BY sequence DESC LIMIT -1 OFFSET ?",
                (MAX_OUTBOX,),
            ).fetchall()
            if rows:
                self.db.executemany("DELETE FROM outbox WHERE id=?", rows)
                count = self.get("dropped", 0) + len(rows)
                self.db.execute(
                    "INSERT OR REPLACE INTO state VALUES ('dropped',?)", (json.dumps(count),)
                )

    def archive_other_sessions(self, session_id, revision):
        rows = self.db.execute("SELECT id,body FROM outbox").fetchall()
        retired = []
        for identity, body in rows:
            message = Message.model_validate_json(body)
            if message.session_id != session_id or message.config_revision != revision:
                retired.append((identity,))
        if retired:
            with self.db:
                self.db.executemany("DELETE FROM outbox WHERE id=?", retired)
            self.set("dropped", self.get("dropped", 0) + len(retired))
            self.set("gap_reason", "configuration_changed_unacknowledged_messages_archived")
        return len(retired)

    def ack(self, message_id):
        with self.db:
            self.db.execute("DELETE FROM outbox WHERE id=?", (message_id,))

    def pending(self):
        return [
            Message.model_validate_json(row[0])
            for row in self.db.execute(
                "SELECT body FROM outbox ORDER BY sequence LIMIT ?", (MAX_OUTBOX,)
            )
        ]

    def cached(self, message_id):
        row = self.db.execute("SELECT replies FROM seen WHERE id=?", (message_id,)).fetchone()
        if row is None:
            return None
        return [Message.model_validate(item) for item in json.loads(row[0])]

    def receive(self, message, replies):
        with self.db:
            self.db.execute(
                "INSERT OR REPLACE INTO seen VALUES (?,?,?)",
                (
                    message.message_id,
                    message.sequence,
                    json.dumps([r.model_dump(by_alias=True) for r in replies]),
                ),
            )
            self._trace("in", message.model_dump_json(by_alias=True))
            self.db.execute(
                "DELETE FROM seen WHERE id IN "
                "(SELECT id FROM seen ORDER BY rowid DESC LIMIT -1 OFFSET ?)",
                (MAX_TRACE,),
            )

    def _trace(self, direction, body):
        self.db.execute("INSERT INTO trace(direction,body) VALUES (?,?)", (direction, body))
        self.db.execute(
            "DELETE FROM trace WHERE ordinal <= (SELECT COALESCE(MAX(ordinal),0)-? FROM trace)",
            (MAX_TRACE,),
        )

    def trace(self):
        return [
            {"direction": d, "message": json.loads(b)}
            for d, b in self.db.execute("SELECT direction,body FROM trace ORDER BY ordinal")
        ]

    def close(self):
        self.db.close()
