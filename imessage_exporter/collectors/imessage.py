"""Collector for Messages (chat.db)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Generator, Iterable, List, Optional
import shutil
import logging

from ..db import connect_readonly
from ..normalize.event import Event, AttachmentRef, Association
from ..normalize.handles import normalize_handle
from ..normalize.time import apple_ts_to_dt_local
from ..identity.person import Person

log = logging.getLogger(__name__)

REACTION_TYPES = {2000}
REPLY_TYPES = {1000}


def _chat_participants(conn, chat_id: int) -> List[str]:
    rows = conn.execute(
        """
        SELECT h.id FROM chat_handle_join ch
        JOIN handle h ON ch.handle_id = h.ROWID
        WHERE ch.chat_id = ?
        """,
        (chat_id,),
    ).fetchall()
    return [normalize_handle(r[0]) for r in rows]


def collect(
    person: Person,
    db_path: Path,
    scope: str = "direct",
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    copy_attachments: bool = False,
    attachments_dir: Optional[Path] = None,
) -> Generator[Event, None, None]:
    conn = connect_readonly(str(db_path))
    handles = person.handles_norm
    if not handles:
        return

    placeholders = ",".join(["?"] * len(handles))
    chat_rows = conn.execute(
        f"""
        SELECT DISTINCT c.ROWID, c.guid
        FROM chat c
        JOIN chat_handle_join ch ON c.ROWID = ch.chat_id
        JOIN handle h ON ch.handle_id = h.ROWID
        WHERE h.id IN ({placeholders})
        """,
        handles,
    ).fetchall()

    for chat_id, chat_guid in chat_rows:
        participants = _chat_participants(conn, chat_id)
        msg_rows = conn.execute(
            """
            SELECT m.ROWID, m.guid, m.date, m.text, m.is_from_me, h.id as handle,
                   m.associated_message_guid, m.associated_message_type
            FROM message m
            LEFT JOIN handle h ON m.handle_id = h.ROWID
            JOIN chat_message_join cm ON cm.message_id = m.ROWID
            WHERE cm.chat_id = ?
            ORDER BY m.date
            """,
            (chat_id,),
        ).fetchall()

        for row in msg_rows:
            guid = row[1]
            ts = apple_ts_to_dt_local(row[2])
            if since and ts < since:
                continue
            if until and ts > until:
                continue
            is_from_me = row[4] == 1
            author = "me" if is_from_me else normalize_handle(row[5]) if row[5] else "unknown"
            if scope == "direct" and not (is_from_me or author in person.handles_norm):
                continue

            association = Association()
            if row[6]:
                if row[7] in REACTION_TYPES:
                    association = Association(type="reaction", target_id=row[6])
                elif row[7] in REPLY_TYPES:
                    association = Association(type="reply", target_id=row[6])

            # attachments
            att_rows = conn.execute(
                """
                SELECT a.filename, a.mime_type, a.transfer_name
                FROM message_attachment_join maj
                JOIN attachment a ON maj.attachment_id = a.ROWID
                WHERE maj.message_id = ?
                """,
                (row[0],),
            ).fetchall()
            attachments = [AttachmentRef(path=r[0], mime=r[1], filename=r[2]) for r in att_rows]
            if copy_attachments and attachments:
                dest_dir = attachments_dir or Path(".")
                dest_dir.mkdir(parents=True, exist_ok=True)
                for att in attachments:
                    try:
                        dest_path = Path(dest_dir) / Path(att.path).name
                        shutil.copy2(att.path, dest_path)
                        att.path = str(dest_path)
                    except Exception as exc:
                        log.warning("attachment copy failed: %s", att.path)

            yield Event(
                id=guid,
                ts=ts,
                source="imessage",
                channel_id=str(chat_guid),
                medium="text" if not association.type else association.type,
                direction="out" if is_from_me else "in",
                author=author,
                participants=participants,
                body=row[3],
                attachments=attachments,
                association=association,
                metadata={"chat_id": chat_id},
            )
