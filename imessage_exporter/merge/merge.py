"""Merge events from multiple collectors."""
from __future__ import annotations

from typing import Iterable, List

from ..normalize.event import Event


def merge_events(*iterables: Iterable[Event]) -> List[Event]:
    seen = {}
    events: List[Event] = []
    for iterable in iterables:
        for ev in iterable:
            if ev.id in seen:
                continue
            seen[ev.id] = ev
            events.append(ev)
    events.sort(key=lambda e: e.ts)
    return events
