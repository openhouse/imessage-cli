"""Person identity representation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Person:
    name: str
    handles_raw: List[str] = field(default_factory=list)
    handles_norm: List[str] = field(default_factory=list)
    raw_to_norm: Dict[str, str] = field(default_factory=dict)
