"""Event schema dataclasses."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class AttachmentRef:
    path: str
    mime: Optional[str] = None
    sha256: Optional[str] = None
    filename: Optional[str] = None


@dataclass
class Association:
    type: Optional[str] = None
    target_id: Optional[str] = None


@dataclass
class Event:
    id: str
    ts: datetime
    source: str
    channel_id: str
    medium: str
    direction: str
    author: str
    participants: List[str]
    body: Optional[str] = None
    mentions: List[str] = field(default_factory=list)
    attachments: List[AttachmentRef] = field(default_factory=list)
    association: Association = field(default_factory=Association)
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        data = asdict(self)
        # dataclasses.asdict handles nested dataclasses
        data["ts"] = self.ts.isoformat()
        return data
