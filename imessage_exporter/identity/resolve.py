"""Resolve a Person from CLI inputs or Contacts."""
from __future__ import annotations

from dataclasses import asdict
from typing import Iterable, List, Optional

from ..normalize.handles import normalize_handle
from .person import Person


def resolve_person(name: str, phones: Optional[Iterable[str]] = None, emails: Optional[Iterable[str]] = None) -> Person:
    phones = list(phones or [])
    emails = list(emails or [])
    handles_raw: List[str] = []
    handles_norm: List[str] = []
    mapping = {}

    for p in phones:
        n = normalize_handle(p)
        handles_raw.append(p)
        handles_norm.append(n)
        mapping[p] = n
    for e in emails:
        n = normalize_handle(e)
        handles_raw.append(e)
        handles_norm.append(n)
        mapping[e] = n

    return Person(name=name, handles_raw=handles_raw, handles_norm=handles_norm, raw_to_norm=mapping)


def preflight_summary(person: Person, sources: Iterable[str], since: Optional[str], until: Optional[str], scope: str) -> str:
    lines = [
        f"Person: {person.name}",
        f"Handles (raw): {', '.join(person.handles_raw)}",
        f"Handles (normalized): {', '.join(person.handles_norm)}",
        f"Sources: {', '.join(sources)}",
        f"Date window: {since or '-∞'} to {until or '∞'}",
        f"Scope: {scope}",
    ]
    return "\n".join(lines)
