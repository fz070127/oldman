"""Durable per-device MQTT outbox."""
import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path


class LocalStore:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, "
                        "payload_json TEXT NOT NULL, sent INTEGER NOT NULL DEFAULT 0, "
                        "created_at TEXT NOT NULL)")
        self.db.execute("CREATE INDEX IF NOT EXISTS pending ON events(sent, created_at)")

    def add(self, event):
        encoded = json.dumps(event, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        with self.lock, self.db:
            self.db.execute("INSERT INTO events(id,payload_json,created_at) VALUES(?,?,?)",
                            (event["eventId"], encoded, datetime.now(timezone.utc).isoformat()))
            victims = self.db.execute("SELECT id,sent FROM events ORDER BY created_at DESC, "
                                      "rowid DESC LIMIT -1 OFFSET 1000").fetchall()
            self.db.executemany("DELETE FROM events WHERE id=?", [(key,) for key, _ in victims])
        for key, sent in victims:
            logging.warning("缓存上限 1000，淘汰 eventId=%s sent=%d", key, sent)

    def oldest(self):
        with self.lock:
            return self.db.execute("SELECT id,payload_json FROM events WHERE sent=0 "
                                   "ORDER BY created_at,rowid LIMIT 1").fetchone()

    def acknowledged(self, key):
        with self.lock, self.db:
            self.db.execute("UPDATE events SET sent=1 WHERE id=?", (key,))

    def close(self):
        self.db.close()
