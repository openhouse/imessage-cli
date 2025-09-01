"""SQLite helpers."""
from __future__ import annotations

import sqlite3
from typing import Iterable

PRAGMAS: Iterable[str] = (
    "PRAGMA query_only=ON",
)


def connect_readonly(path: str) -> sqlite3.Connection:
    """Return a read-only SQLite connection with safe pragmas."""
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    for pragma in PRAGMAS:
        conn.execute(pragma)
    return conn
