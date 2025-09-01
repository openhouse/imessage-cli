"""JSON Lines renderer."""
from __future__ import annotations

import json
from typing import Iterable, TextIO

from ..normalize.event import Event


def render(events: Iterable[Event], fh: TextIO) -> None:
    for ev in events:
        fh.write(json.dumps(ev.to_dict()) + "\n")
        fh.flush()
