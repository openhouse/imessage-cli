from __future__ import annotations

from pathlib import Path
import sqlite3
from datetime import datetime

from ..eventlog import EventLog
from ..hlc import HLC
from ..schema import EventKind, MessageEvent
from ..trust import BridgeMode
from ..db import connect_readonly
from ..normalize.time import apple_ts_to_dt_local


def ingest_chatdb(
    db_path: Path,
    person_did: str,
    log: EventLog,
    hlc: HLC,
) -> None:
    conn = connect_readonly(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    for row in cur.execute(
        "SELECT ROWID as rowid, guid, text, date, is_from_me FROM message ORDER BY date"
    ):
        ts = apple_ts_to_dt_local(row["date"])
        # attachments references
        att_rows = cur.execute(
            """
            SELECT a.transfer_name, a.mime_type, a.filename
            FROM message_attachment_join maj
            JOIN attachment a ON maj.attachment_id = a.ROWID
            WHERE maj.message_id = ?
            """,
            (row["rowid"],),
        ).fetchall()
        attachments = [{"name": r[0], "mime": r[1], "uri": r[2]} for r in att_rows]
        event = MessageEvent(
            event_id=row["guid"],
            kind=EventKind.MESSAGE,
            person_did=person_did,
            source={
                "service": "imessage",
                "id": row["guid"],
                "sender": "me" if row["is_from_me"] else "other",
            },
            time_event=ts,
            time_observed=datetime.utcnow(),
            hlc=hlc.now(),
            security={"e2e": False, "bridge_mode": BridgeMode.ON_DEVICE.value},
            provenance=[f"imessage.message {row['rowid']}"],
            tombstone=None,
            body={"text": row["text"], "format": "plain"},
            rel={},
            attachments=attachments,
        )
        log.append_event(event)
    conn.close()
