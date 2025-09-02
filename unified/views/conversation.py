from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Tuple

from ..eventlog import iter_events
from ..schema import BaseEvent, EventKind
from ..trust import TrustBadge
from ..hlc import HLC
from ..sanitize import clean_urls, has_url, normalize_handle


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
    *,
    group_by_conversation: bool = True,
    via_collapse: bool = False,
    resolve_display: Callable[[str | None, str | None], str] | None = None,
    hide_plugin_payload: bool = True,
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
    # Helper for dedupe
    def normalize_text(s: str) -> str:
        return (s or "").strip()

    def fp_key(text: str, when_iso: str, who: str | None) -> str:
        # Round to nearest 120s to tolerate slight skews
        try:
            dt = datetime.fromisoformat(when_iso)
        except Exception:
            dt = datetime.fromisoformat(when_iso.replace("Z", "+00:00"))
        epoch = int(dt.timestamp())
        rounded = datetime.fromtimestamp((epoch // 120) * 120, tz=dt.tzinfo)
        base = f"{normalize_text(text)}|{rounded.isoformat()}|{who or ''}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()

    seen: Dict[str, dict] = {}
    for ev in events:
        if ev.kind == EventKind.MESSAGE:
            me = ev  # type: MessageEvent
            conversation_id = (me.rel or {}).get("conversation_id")
            who_raw = me.source.get("sender")
            display_who = (
                resolve_display(who_raw, me.source.get("display_name"))
                if resolve_display
                else (who_raw or "other")
            )
            raw_text = me.body.get("text", "")
            text = clean_urls(raw_text)
            atts = me.attachments if "attachments" in include else []
            if hide_plugin_payload and has_url(text):
                atts = [a for a in atts if not str(a.get("name", "")).endswith(".pluginPayloadAttachment")]
            base_item = {
                "timestamp": me.time_event.isoformat(),
                "who": display_who,
                "who_handle": who_raw,
                "kind": "message",
                "text": text,
                "attachments": atts,
                "rel": me.rel,
                "conversation_id": conversation_id,
                "trust_badge": _badge_for(me),
                "provenance": me.provenance,
                "via": [me.source.get("route") or me.source.get("service")],
                "reactions": [],
            }
            if via_collapse:
                k = fp_key(base_item["text"], base_item["timestamp"], who_raw)
                existing = seen.get(k)
                if existing:
                    for v in base_item["via"]:
                        if v and v not in existing["via"]:
                            existing["via"].append(v)
                    existing["provenance"].extend(
                        x for x in base_item["provenance"] if x not in existing["provenance"]
                    )
                    index[me.event_id] = existing
                else:
                    seen[k] = base_item
                    items.append(base_item)
                    index[me.event_id] = base_item
            else:
                items.append(base_item)
                index[me.event_id] = base_item
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

    # Optionally group by conversation with headers (objects mode can still include)
    if group_by_conversation and output != "jsonl":
        grouped: Dict[str | None, List[dict]] = {}
        meta: Dict[str | None, dict] = {}
        for it in items:
            cid = it.get("conversation_id")
            grouped.setdefault(cid, []).append(it)
            rel = it.get("rel") or {}
            participants = rel.get("participants") or []
            names = []
            for h in participants:
                if resolve_display:
                    names.append(resolve_display(h, None))
                else:
                    names.append(h)
            meta.setdefault(cid, {"participants": sorted(set(names))})
        flattened: List[dict] = []
        for cid, rows in grouped.items():
            header = {
                "kind": "header",
                "conversation_id": cid,
                "participants": meta.get(cid, {}).get("participants", []),
            }
            flattened.append(header)
            flattened.extend(rows)
        items = flattened

    if output == "jsonl":
        return (json.dumps(it, sort_keys=True) for it in items)
    return items


def list_chats(person_did: str, resolve_display: Callable[[str | None, str | None], str] | None = None) -> List[dict]:
    chats: Dict[str, dict] = {}
    for ev in iter_events(person_did):
        if ev.kind != EventKind.MESSAGE:
            continue
        rel = getattr(ev, "rel", {}) or {}
        cid = rel.get("conversation_id")
        if not cid:
            continue
        meta = chats.setdefault(cid, {"participants": set(), "count": 0})
        meta["count"] += 1
        for h in rel.get("participants") or []:
            name = resolve_display(h, None) if resolve_display else h
            meta["participants"].add(name)
    out: List[dict] = []
    for cid, meta in chats.items():
        out.append(
            {
                "conversation_id": cid,
                "participants": sorted(meta["participants"]),
                "count": meta["count"],
            }
        )
    return sorted(out, key=lambda d: d["conversation_id"])  # deterministic order


def render_markdown(
    person_did: str,
    conversation_id: str,
    resolve_display: Callable[[str | None, str | None], str] | None = None,
    show_handles: bool = False,
    hide_plugin_payload: bool = True,
    via_collapse: bool = False,
) -> str:
    items = list(
        get_conversation(
            person_did,
            output="objects",
            group_by_conversation=True,
            via_collapse=via_collapse,
            resolve_display=resolve_display,
            hide_plugin_payload=hide_plugin_payload,
        )
    )
    lines: List[str] = []
    participants: List[str] = []
    collecting = False
    for it in items:
        if it.get("kind") == "header":
            collecting = it.get("conversation_id") == conversation_id
            if collecting:
                participants = it.get("participants", [])
                lines.append(f"# Thread: {conversation_id}")
                lines.append("Participants: " + ", ".join(participants))
                lines.append("")
            continue
        if not collecting:
            continue
        who = it.get("who")
        handle = it.get("who_handle")
        if show_handles and handle not in (None, "me"):
            who = f"{who} ({normalize_handle(handle)})"
        lines.append(f"{it['timestamp']} — {who}: {it.get('text', '')}")
    return "\n".join(lines)
