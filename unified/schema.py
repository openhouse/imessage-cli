from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Type, TypeVar


class EventKind(str, Enum):
    MESSAGE = "Message"
    EDIT = "Edit"
    DELETE = "Delete"
    REACTION = "Reaction"
    ATTACHMENT = "Attachment"
    READ_RECEIPT = "ReadReceipt"
    CALL = "Call"
    MEMBERSHIP = "Membership"


@dataclass(kw_only=True)
class BaseEvent:
    event_id: str
    kind: EventKind
    person_did: str
    source: Dict[str, Any]
    time_event: datetime
    time_observed: datetime
    hlc: str
    security: Dict[str, Any]
    provenance: List[str]
    tombstone: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["kind"] = self.kind.value
        data["time_event"] = self.time_event.isoformat()
        data["time_observed"] = self.time_observed.isoformat()
        return data


@dataclass
class MessageEvent(BaseEvent):
    body: Dict[str, Any]
    rel: Dict[str, Any]
    attachments: List[Dict[str, Any]]


@dataclass
class EditEvent(BaseEvent):
    target_event_id: str
    patch: Dict[str, Any]


@dataclass
class DeleteEvent(BaseEvent):
    target_event_id: str


@dataclass
class ReactionEvent(BaseEvent):
    target_event_id: str
    reaction: str


@dataclass
class CallEvent(BaseEvent):
    direction: str
    duration_ms: Optional[int]


T = TypeVar("T", bound=BaseEvent)


def _common_from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
    data = data.copy()
    data["kind"] = EventKind(data["kind"])
    data["time_event"] = datetime.fromisoformat(data["time_event"])
    data["time_observed"] = datetime.fromisoformat(data["time_observed"])
    return cls(**data)  # type: ignore[arg-type]


def event_from_dict(data: Dict[str, Any]) -> BaseEvent:
    kind = EventKind(data["kind"])
    mapping: Dict[EventKind, Type[BaseEvent]] = {
        EventKind.MESSAGE: MessageEvent,
        EventKind.EDIT: EditEvent,
        EventKind.DELETE: DeleteEvent,
        EventKind.REACTION: ReactionEvent,
        EventKind.CALL: CallEvent,
    }
    cls = mapping.get(kind, BaseEvent)
    return _common_from_dict(cls, data)
