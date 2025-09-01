"""Collector for call history."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Generator, Optional

from ..db import connect_readonly
from ..normalize.event import Event, Association
from ..normalize.handles import normalize_handle
from ..normalize.time import apple_ts_to_dt_local
from ..identity.person import Person


DIRECTION_MAP = {
    1: "out",
    2: "in",
    3: "missed",
}


def collect(
    person: Person,
    db_path: Path,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> Generator[Event, None, None]:
    conn = connect_readonly(str(db_path))
    rows = conn.execute(
        """
        SELECT rowid, address, date, duration, flags
        FROM call
        WHERE address IS NOT NULL
        ORDER BY date
        """
    ).fetchall()
    for row in rows:
        handle_norm = normalize_handle(row[1])
        if handle_norm not in person.handles_norm:
            continue
        ts = apple_ts_to_dt_local(row[2])
        if since and ts < since:
            continue
        if until and ts > until:
            continue
        direction = DIRECTION_MAP.get(row[4], "in")
        yield Event(
            id=f"call:{row[0]}:{row[2]}",
            ts=ts,
            source="facetime",
            channel_id="",
            medium="call",
            direction=direction,
            author="me" if direction == "out" else handle_norm,
            participants=["me", handle_norm],
            metadata={"duration": row[3]},
            association=Association(),
            body=None,
            mentions=[],
            attachments=[],
        )
