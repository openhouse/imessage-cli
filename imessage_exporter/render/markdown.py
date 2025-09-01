"""Markdown renderer."""
from __future__ import annotations

from typing import Iterable, TextIO

from ..normalize.event import Event


def render(events: Iterable[Event], fh: TextIO) -> None:
    for ev in events:
        ts = ev.ts.isoformat()
        author = ev.author
        body = ev.body or ""
        line = f"* {ts} {author}: {body} ({ev.id})\n"
        fh.write(line)
        fh.flush()
