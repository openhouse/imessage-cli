from __future__ import annotations

import json
from datetime import datetime
from typing import List, Tuple

from ..eventlog import iter_events
from ..schema import BaseEvent, EventKind
from ..trust import TrustBadge
from ..hlc import HLC


def _badge_for(event: BaseEvent) -> str:
    service = event.source.get("service")
    if service == "imessage":
        return TrustBadge.LOCALLY_DECRYPTED.value
    if service == "email":
        return TrustBadge.PLAIN.value
    return TrustBadge.UNKNOWN.value


def get_conversation(
    person_did: str,
    since: datetime | None = None,
    until: datetime | None = None,
    include: Tuple[str, ...] = ("messages", "calls", "attachments", "reactions"),
    output: str = "objects",
):
    events = list(iter_events(person_did, since, until))
    events.sort(
        key=lambda e: (
            *HLC._parse(e.hlc)[:2],
            e.time_event.isoformat(),
            e.event_id,
        )
    )
    items: List[dict] = []
    index: dict[str, dict] = {}
    for ev in events:
        if ev.kind == EventKind.MESSAGE:
            me = ev  # type: MessageEvent
            item = {
                "timestamp": me.time_event.isoformat(),
                "who": me.source.get("sender", "other"),
                "kind": "message",
                "text": me.body.get("text", ""),
                "attachments": me.attachments if "attachments" in include else [],
                "rel": me.rel,
                "trust_badge": _badge_for(me),
                "provenance": me.provenance,
                "reactions": [],
            }
            items.append(item)
            index[me.event_id] = item
        elif ev.kind == EventKind.EDIT:
            ee = ev  # type: EditEvent
            target = index.get(ee.target_event_id)
            if target:
                target["text"] = ee.patch.get("text", target.get("text", ""))
        elif ev.kind == EventKind.DELETE:
            de = ev  # type: DeleteEvent
            target = index.get(de.target_event_id)
            if target:
                target["tombstone"] = de.tombstone or {"reason": "deleted"}
        elif ev.kind == EventKind.REACTION:
            re = ev  # type: ReactionEvent
            target = index.get(re.target_event_id)
            if target and "reactions" in include:
                if "reactions" not in target:
                    target["reactions"] = []
                if re.reaction not in target["reactions"]:
                    target["reactions"].append(re.reaction)
        elif ev.kind == EventKind.CALL:
            ce = ev  # type: CallEvent
            item = {
                "timestamp": ce.time_event.isoformat(),
                "who": ce.source.get("sender", "other"),
                "kind": "call",
                "direction": ce.direction,
                "duration_ms": ce.duration_ms,
                "trust_badge": _badge_for(ce),
                "provenance": ce.provenance,
            }
            items.append(item)
    if output == "jsonl":
        return (json.dumps(it, sort_keys=True) for it in items)
    return items
