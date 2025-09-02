from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

from .schema import BaseEvent, event_from_dict

DEFAULT_DB_PATH = Path.home() / ".imx/unified/events.db"


class SQLiteEventStore:
    def __init__(self, path: Path = DEFAULT_DB_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(self.path.parent, 0o700)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS events(
                event_id TEXT PRIMARY KEY,
                kind TEXT,
                person_did TEXT,
                service TEXT,
                source_id TEXT,
                time_event TEXT,
                time_observed TEXT,
                hlc TEXT,
                e2e INTEGER,
                bridge_mode TEXT,
                body_json TEXT,
                rel_json TEXT,
                attachments_json TEXT,
                tombstone_json TEXT,
                provenance_json TEXT
            )
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_person_time ON events(person_did, time_event)"
        )
        try:
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_conv_time ON events(json_extract(body_json, '$.rel.conversation_id'), time_event)"
            )
        except sqlite3.OperationalError:
            pass
        self.conn.commit()

    def append(self, event: BaseEvent) -> None:
        data = event.to_dict()
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT OR REPLACE INTO events(
                event_id, kind, person_did, service, source_id,
                time_event, time_observed, hlc, e2e, bridge_mode,
                body_json, rel_json, attachments_json, tombstone_json, provenance_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                data["event_id"],
                data["kind"],
                data["person_did"],
                event.source.get("service", ""),
                event.source.get("id", ""),
                data["time_event"],
                data["time_observed"],
                data["hlc"],
                int(event.security.get("e2e", False)),
                event.security.get("bridge_mode", ""),
                json.dumps(data),
                None,
                None,
                json.dumps(data.get("tombstone")),
                json.dumps(data.get("provenance")),
            ),
        )
        self.conn.commit()

    def iter_events(
        self,
        person_did: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> Iterator[BaseEvent]:
        cur = self.conn.cursor()
        query = "SELECT body_json FROM events WHERE person_did=?"
        params: list[str] = [person_did]
        if since is not None:
            query += " AND time_event >= ?"
            params.append(since.isoformat())
        if until is not None:
            query += " AND time_event <= ?"
            params.append(until.isoformat())
        query += " ORDER BY time_event"
        for row in cur.execute(query, params):
            data = json.loads(row["body_json"])
            yield event_from_dict(data)

    def contains(self, event_id: str) -> bool:
        cur = self.conn.cursor()
        cur.execute("SELECT 1 FROM events WHERE event_id=?", (event_id,))
        return cur.fetchone() is not None
