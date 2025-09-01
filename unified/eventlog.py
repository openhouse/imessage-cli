from __future__ import annotations

from datetime import datetime
from typing import Iterator, Optional

from .schema import BaseEvent
from .storage_sqlite import SQLiteEventStore


class EventLog:
    def __init__(self, store: SQLiteEventStore | None = None) -> None:
        self.store = store or SQLiteEventStore()

    def append_event(self, event: BaseEvent) -> None:
        self.store.append(event)

    def iter_events(
        self,
        person_did: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> Iterator[BaseEvent]:
        return self.store.iter_events(person_did, since, until)

    def contains(self, event_id: str) -> bool:
        return self.store.contains(event_id)


default_log = EventLog()


def append_event(event: BaseEvent) -> None:
    default_log.append_event(event)


def iter_events(
    person_did: str, since: Optional[datetime] = None, until: Optional[datetime] = None
) -> Iterator[BaseEvent]:
    yield from default_log.iter_events(person_did, since, until)


def contains(event_id: str) -> bool:
    return default_log.contains(event_id)
