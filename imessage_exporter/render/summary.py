"""Summary renderer."""
from __future__ import annotations

from datetime import datetime
from typing import Iterable, Dict

from ..normalize.event import Event


SCHEMA_VERSION = 1


def render(events: Iterable[Event]) -> Dict:
    events = list(events)
    messages_exported = len(events)
    first_ts = events[0].ts.isoformat() if events else None
    last_ts = events[-1].ts.isoformat() if events else None
    return {
        "messages_total": messages_exported,
        "messages_exported": messages_exported,
        "reactions_skipped": 0,
        "attachments_copied": 0,
        "first_ts": first_ts,
        "last_ts": last_ts,
        "sources": sorted({e.source for e in events}),
        "schema_version": SCHEMA_VERSION,
        "version": "0.1",
    }
