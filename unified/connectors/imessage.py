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

    # Pull sender handle and room; we may get multiple chat rows per message (multi-room edge cases)
    q = """
    SELECT
      m.ROWID                  AS rowid,
      m.guid                   AS msg_guid,
      m.text                   AS text,
      m.date                   AS date,
      m.is_from_me             AS is_from_me,
      h.id                     AS sender_handle,
      h.service                AS sender_service,
      c.guid                   AS chat_guid,
      c.chat_identifier        AS chat_identifier
    FROM message m
    LEFT JOIN handle h           ON h.ROWID = m.handle_id
    LEFT JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
    LEFT JOIN chat c             ON c.ROWID = cmj.chat_id
    ORDER BY m.date, m.ROWID;
    """

    # Preload participants per chat_id to avoid N+1 lookups
    participants_cache: dict[str, list[str]] = {}

    def participants_for(chat_guid: str) -> list[str]:
        if not chat_guid:
            return []
        if chat_guid in participants_cache:
            return participants_cache[chat_guid]
        rows = conn.execute(
            """
            SELECT h.id
            FROM chat
            JOIN chat_handle_join chj ON chj.chat_id = chat.ROWID
            JOIN handle h             ON h.ROWID = chj.handle_id
            WHERE chat.guid = ?
            """,
            (chat_guid,),
        ).fetchall()
        vals = sorted({r["id"] for r in rows})
        participants_cache[chat_guid] = vals
        return vals

    for row in cur.execute(q):
        ts = apple_ts_to_dt_local(row["date"])
        chat_guid = row["chat_guid"] or ""

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

        # Sender: for is_from_me==0 the actual sender is handle.id; else "me"
        sender = "me" if row["is_from_me"] else (row["sender_handle"] or "unknown")
        event = MessageEvent(
            event_id=row["msg_guid"],
            kind=EventKind.MESSAGE,
            person_did=person_did,
            source={
                "service": "imessage",
                "id": row["msg_guid"],
                "sender": sender,
                "chat_guid": chat_guid,
                "route": f"imessage:{row['sender_service'] or 'unknown'}",
            },
            time_event=ts,
            time_observed=datetime.utcnow(),
            hlc=hlc.now(),
            security={"e2e": False, "bridge_mode": BridgeMode.ON_DEVICE.value},
            provenance=[f"imessage.message {row['rowid']}"],
            tombstone=None,
            body={"text": row["text"], "format": "plain"},
            rel={
                "conversation_id": f"imessage:chat:{chat_guid}" if chat_guid else None,
                "participants": participants_for(chat_guid),
            },
            attachments=attachments,
        )
        log.append_event(event)
    conn.close()
