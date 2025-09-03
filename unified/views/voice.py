from __future__ import annotations

from collections import defaultdict
import hashlib
from datetime import datetime
from typing import Callable, Dict, List, Set, Tuple

from ..eventlog import iter_events
from ..hlc import HLC
from ..identity.contacts import expand_handles, normalize_handle_for_matching
from ..sanitize import clean_urls, has_url
from ..schema import EventKind, MessageEvent


def _fp_key(text: str, when: datetime, who: str | None) -> str:
    epoch = int(when.timestamp())
    rounded = datetime.fromtimestamp((epoch // 120) * 120, tz=when.tzinfo)
    base = f"{text.strip()}|{rounded.isoformat()}|{who or ''}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def _merge_ranges(ranges: List[Tuple[int, int]]) -> Set[int]:
    if not ranges:
        return set()
    ranges.sort()
    merged: List[Tuple[int, int]] = []
    for start, end in ranges:
        if not merged or start > merged[-1][1] + 1:
            merged.append([start, end])  # type: ignore[list-item]
        else:
            merged[-1][1] = max(merged[-1][1], end)  # type: ignore[index]
    keep: Set[int] = set()
    for s, e in merged:
        keep.update(range(s, e + 1))
    return keep


def render_voice_manuscript(
    person_did: str,
    seed: str,
    since: datetime | None = None,
    until: datetime | None = None,
    *,
    context: int = 2,
    quotes_only: bool = False,
    show_handles: bool = False,
    via_collapse: bool = False,
    hide_plugin_payload: bool = True,
    resolve_display: Callable[[str | None, str | None], str] | None = None,
) -> str:
    display_name, handles, _ = expand_handles(seed)

    buckets: Dict[str | None, List[MessageEvent]] = defaultdict(list)
    for ev in iter_events(person_did, since, until):
        if ev.kind != EventKind.MESSAGE:
            continue
        me = ev  # type: MessageEvent
        cid = (me.rel or {}).get("conversation_id")
        buckets[cid].append(me)

    room_blocks: List[Tuple[datetime, str | None, List[str]]] = []
    all_lines: List[str] = []
    overall_start: datetime | None = None
    overall_end: datetime | None = None

    for cid, events in buckets.items():
        events.sort(
            key=lambda e: (
                *HLC._parse(e.hlc)[:2],
                e.time_event.isoformat(),
                e.event_id,
            )
        )
        authored_idx = [
            i
            for i, e in enumerate(events)
            if normalize_handle_for_matching(e.source.get("sender")) in handles
        ]
        if not authored_idx:
            continue
        if quotes_only:
            keep_idx = set(authored_idx)
        else:
            ranges = []
            for i in authored_idx:
                s = max(0, i - context)
                e = min(len(events) - 1, i + context)
                ranges.append((s, e))
            keep_idx = _merge_ranges(ranges)

        seen: Dict[str, Tuple[int, MessageEvent, List[str]]] = {}
        kept: List[Tuple[int, MessageEvent]] = []
        for i, ev in enumerate(events):
            if i not in keep_idx:
                continue
            if via_collapse:
                who_norm = normalize_handle_for_matching(ev.source.get("sender"))
                key = _fp_key(clean_urls(ev.body.get("text", "")), ev.time_event, who_norm)
                route = ev.source.get("route") or ev.source.get("service")
                existing = seen.get(key)
                if existing:
                    if route and route not in existing[2]:
                        existing[2].append(route)
                    continue
                else:
                    seen[key] = (i, ev, [r for r in [route] if r])
            kept.append((i, ev))
        if via_collapse:
            kept = [seen[k][:2] for k in seen]
            via_map = {id(ev): seen[k][2] for k, (_, ev, _) in seen.items()}
        else:
            via_map = {}

        participant_handles: Set[str] = set()
        for ev in events:
            for h in (ev.rel or {}).get("participants") or []:
                participant_handles.add(h)
        participants: List[str] = []
        for h in sorted(participant_handles):
            participants.append(resolve_display(h, None) if resolve_display else h)

        header = []
        convo_name = (events[0].source.get("chat_name") or (events[0].rel or {}).get("conversation_name") or cid)
        header.append(f"## Room: {convo_name}")
        header.append("Participants: " + ", ".join(participants))
        header.append("")
        body_lines: List[str] = []
        for i, ev in sorted(kept, key=lambda t: t[0]):
            sender = ev.source.get("sender")
            who = (
                resolve_display(sender, ev.source.get("display_name"))
                if resolve_display
                else (sender or "Unknown")
            )
            norm = normalize_handle_for_matching(sender) if sender else ""
            if show_handles and sender not in (None, "me"):
                who = f"{who} ({norm})"
            text = clean_urls(ev.body.get("text", ""))
            attachments = ev.attachments
            if hide_plugin_payload and has_url(text):
                attachments = [a for a in attachments if not str(a.get("name", "")).endswith(".pluginPayloadAttachment")]
            att_txt = "".join(f" [attachment: {a.get('name')}]" for a in attachments)
            who_fmt = f"**{who}**" if i in authored_idx else who
            ts = ev.time_event.strftime("%Y-%m-%d %H:%M")
            via = ""
            if via_collapse:
                vias = via_map.get(id(ev), [])
                if vias:
                    via = f" (via {', '.join(sorted(set(vias)))})"
            body_lines.append(f"{ts} — {who_fmt}: {text}{att_txt}{via}")
            if overall_start is None or ev.time_event < overall_start:
                overall_start = ev.time_event
            if overall_end is None or ev.time_event > overall_end:
                overall_end = ev.time_event
        body_lines.append("")
        block = header + body_lines
        first_time = events[kept[0][0]].time_event if kept else events[0].time_event
        room_blocks.append((first_time, cid, block))

    room_blocks.sort(key=lambda t: t[0])
    for _, _, blk in room_blocks:
        all_lines.extend(blk)

    handles_str = ", ".join(sorted(handles))
    if overall_start and overall_end:
        range_s = overall_start.date().isoformat()
        range_e = overall_end.date().isoformat()
    else:
        range_s = range_e = "unknown"
    top = [f"# Voice: {display_name}", f"Handles: {handles_str}   Range: {range_s} → {range_e}", ""]
    return "\n".join(top + all_lines)

