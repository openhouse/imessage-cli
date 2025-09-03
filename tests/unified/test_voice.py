from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from unified.eventlog import EventLog
from unified import eventlog as eventlog_module
from unified.hlc import HLC
from unified.schema import EventKind, MessageEvent
from unified.storage_sqlite import SQLiteEventStore
from unified.views.voice import render_voice_manuscript
from unified.identity import contacts
from unified.identity.contacts import normalize_handle_for_matching


def _msg(event_id, who, cid, text, t, hlc, service="imessage", route="imessage:sms", attachments=None, participants=None):
    return MessageEvent(
        event_id=event_id,
        kind=EventKind.MESSAGE,
        person_did="did:person:test",
        source={"service": service, "id": event_id, "sender": who, "route": route},
        time_event=t,
        time_observed=t,
        hlc=hlc.now(),
        security={"e2e": False, "bridge_mode": "NONE"},
        provenance=[f"{service} row"],
        tombstone=None,
        body={"text": text, "format": "plain"},
        rel={"conversation_id": cid, "participants": participants or [who, "me"]},
        attachments=attachments or [],
    )


def _setup(tmp_path: Path) -> tuple[EventLog, HLC]:
    store = SQLiteEventStore(path=tmp_path / "events.db")
    log = EventLog(store)
    eventlog_module.default_log = log
    return log, HLC()


def _people(tmp_path: Path, data: dict) -> None:
    p = tmp_path / "people.json"
    p.write_text(json.dumps(data))
    contacts.PEOPLE_PATH = p
    contacts.DEFAULT_VCF = None
    contacts.DEFAULT_CSV = None


def test_voice_same_from_email_and_phone(tmp_path):
    _people(
        tmp_path,
        {
            "Lindsey": {
                "label": "Lindsey Griffith",
                "handles": [
                    "mailto:lindseyagriffith@gmail.com",
                    "tel:+13169921361",
                ],
            }
        },
    )
    log, hlc = _setup(tmp_path)
    t = datetime(2021, 1, 1, 12, 0, 0)
    log.append_event(_msg("m1", "+13169921361", "imessage:chat:1", "hi", t, hlc))
    log.append_event(
        _msg(
            "m2",
            "lindseyagriffith@gmail.com",
            "email:thread:2",
            "hi",
            t + timedelta(minutes=1),
            hlc,
            service="email",
            route="email",
        )
    )
    md_phone = render_voice_manuscript(
        "did:person:test",
        "+13169921361",
        context=0,
        resolve_display=lambda h, _: h,
    )
    md_email = render_voice_manuscript(
        "did:person:test",
        "lindseyagriffith@gmail.com",
        context=0,
        resolve_display=lambda h, _: h,
    )
    assert md_phone == md_email


def test_voice_context_window_merge(tmp_path):
    _people(tmp_path, {"P": {"label": "P", "handles": ["tel:+1000"]}})
    log, hlc = _setup(tmp_path)
    t = datetime(2021, 1, 1, 12, 0, 0)
    cid = "imessage:chat:room"
    log.append_event(_msg("a", "Bob", cid, "0", t, hlc))
    log.append_event(_msg("b", "+1000", cid, "1", t + timedelta(seconds=1), hlc))
    log.append_event(_msg("c", "Bob", cid, "2", t + timedelta(seconds=2), hlc))
    log.append_event(_msg("d", "+1000", cid, "3", t + timedelta(seconds=3), hlc))
    log.append_event(_msg("e", "Bob", cid, "4", t + timedelta(seconds=4), hlc))
    md = render_voice_manuscript(
        "did:person:test",
        "+1000",
        context=1,
        resolve_display=lambda h, _: h,
    )
    lines = [ln for ln in md.splitlines() if "—" in ln]
    assert len(lines) == 5


def test_quotes_only(tmp_path):
    _people(tmp_path, {"P": {"label": "P", "handles": ["tel:+1000"]}})
    log, hlc = _setup(tmp_path)
    t = datetime(2021, 1, 1, 12, 0, 0)
    cid = "imessage:chat:room"
    log.append_event(_msg("a", "Bob", cid, "0", t, hlc))
    log.append_event(_msg("b", "+1000", cid, "1", t + timedelta(seconds=1), hlc))
    log.append_event(_msg("c", "Bob", cid, "2", t + timedelta(seconds=2), hlc))
    md = render_voice_manuscript(
        "did:person:test",
        "+1000",
        quotes_only=True,
        resolve_display=lambda h, _: h,
    )
    lines = [ln for ln in md.splitlines() if "—" in ln]
    # Only one utterance from target
    assert len(lines) == 1


def test_handle_normalization_controls():
    dirty = "+‪13169921361‬"
    clean = "+13169921361"
    assert normalize_handle_for_matching(dirty) == normalize_handle_for_matching(clean)


def test_plugin_preview_filter_in_voice(tmp_path):
    _people(tmp_path, {"P": {"label": "P", "handles": ["tel:+1000"]}})
    log, hlc = _setup(tmp_path)
    t = datetime(2021, 1, 1, 12, 0, 0)
    cid = "imessage:chat:room"
    log.append_event(
        _msg(
            "a",
            "+1000",
            cid,
            "see https://example.com",
            t,
            hlc,
            attachments=[{"name": "preview.pluginPayloadAttachment"}],
        )
    )
    log.append_event(
        _msg(
            "b",
            "+1000",
            cid,
            "no link",
            t + timedelta(seconds=1),
            hlc,
            attachments=[{"name": "keep.pluginPayloadAttachment"}],
        )
    )
    md = render_voice_manuscript(
        "did:person:test",
        "+1000",
        context=0,
        resolve_display=lambda h, _: h,
    )
    lines = [ln for ln in md.splitlines() if "—" in ln]
    assert "attachment: preview.pluginPayloadAttachment" not in lines[0]
    assert "attachment: keep.pluginPayloadAttachment" in lines[1]


def test_via_collapse_opt_in(tmp_path):
    _people(tmp_path, {"P": {"label": "P", "handles": ["tel:+1000"]}})
    log, hlc = _setup(tmp_path)
    t = datetime(2021, 1, 1, 12, 0, 0)
    cid = "imessage:chat:room"
    log.append_event(_msg("a", "+1000", cid, "hi", t, hlc, route="sms"))
    log.append_event(_msg("b", "+1000", cid, "hi", t + timedelta(seconds=30), hlc, route="imessage"))
    md_no = render_voice_manuscript(
        "did:person:test",
        "+1000",
        context=0,
        resolve_display=lambda h, _: h,
    )
    md_yes = render_voice_manuscript(
        "did:person:test",
        "+1000",
        context=0,
        via_collapse=True,
        resolve_display=lambda h, _: h,
    )
    lines_no = [ln for ln in md_no.splitlines() if "—" in ln]
    lines_yes = [ln for ln in md_yes.splitlines() if "—" in ln]
    assert len(lines_no) == 2
    assert len(lines_yes) == 1


def test_stable_ordering(tmp_path):
    _people(tmp_path, {"P": {"label": "P", "handles": ["tel:+1000"]}})
    log, hlc = _setup(tmp_path)
    t = datetime(2021, 1, 1, 12, 0, 0)
    cid = "imessage:chat:room"
    # Generate two HLC values
    hlc1 = hlc.now()
    hlc2 = hlc.now()
    msg1 = MessageEvent(
        event_id="a",
        kind=EventKind.MESSAGE,
        person_did="did:person:test",
        source={"service": "imessage", "id": "a", "sender": "+1000", "route": "sms"},
        time_event=t,
        time_observed=t,
        hlc=hlc1,
        security={"e2e": False, "bridge_mode": "NONE"},
        provenance=["imessage row"],
        tombstone=None,
        body={"text": "first", "format": "plain"},
        rel={"conversation_id": cid, "participants": ["+1000", "me"]},
        attachments=[],
    )
    msg2 = MessageEvent(
        event_id="b",
        kind=EventKind.MESSAGE,
        person_did="did:person:test",
        source={"service": "imessage", "id": "b", "sender": "+1000", "route": "sms"},
        time_event=t,
        time_observed=t,
        hlc=hlc2,
        security={"e2e": False, "bridge_mode": "NONE"},
        provenance=["imessage row"],
        tombstone=None,
        body={"text": "second", "format": "plain"},
        rel={"conversation_id": cid, "participants": ["+1000", "me"]},
        attachments=[],
    )
    # Append out of order
    log.append_event(msg2)
    log.append_event(msg1)
    md = render_voice_manuscript(
        "did:person:test",
        "+1000",
        context=0,
        resolve_display=lambda h, _: h,
    )
    lines = [ln for ln in md.splitlines() if "—" in ln]
    assert "first" in lines[0]
    assert "second" in lines[1]

