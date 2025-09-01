from __future__ import annotations

from .schema import BaseEvent


def add_provenance(event: BaseEvent, note: str) -> None:
    event.provenance.append(note)
