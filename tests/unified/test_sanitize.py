from datetime import datetime

from unified.sanitize import clean_urls, has_url, normalize_handle
from unified.eventlog import EventLog
from unified import eventlog as eventlog_module
from unified.hlc import HLC
from unified.schema import EventKind, MessageEvent
from unified.storage_sqlite import SQLiteEventStore
from unified.views.conversation import get_conversation
from unified.cli import unify as unify_cli


def test_clean_urls():
    assert clean_urls("Khttps://x.y/WHttpURL/") == "https://x.y/"
    assert clean_urls("ttps://y") == "https://y"


def test_plugin_payload_hidden_on_url(tmp_path):
    store = SQLiteEventStore(path=tmp_path / "events.db")
    log = EventLog(store)
    eventlog_module.default_log = log
    hlc = HLC()
    now = datetime.utcnow()
    # message with URL and plugin attachment
    log.append_event(
        MessageEvent(
            event_id="a",
            kind=EventKind.MESSAGE,
            person_did="did:person:test",
            source={"service": "imessage", "id": "a", "sender": "+1"},
            time_event=now,
            time_observed=now,
            hlc=hlc.now(),
            security={"e2e": False, "bridge_mode": "NONE"},
            provenance=["p"],
            tombstone=None,
            body={"text": "check https://example.com", "format": "plain"},
            rel={"conversation_id": "chat1", "participants": ["+1"]},
            attachments=[{"name": "link.pluginPayloadAttachment", "mime": "text/html", "uri": "p"}],
        )
    )
    # message without URL but plugin attachment
    log.append_event(
        MessageEvent(
            event_id="b",
            kind=EventKind.MESSAGE,
            person_did="did:person:test",
            source={"service": "imessage", "id": "b", "sender": "+1"},
            time_event=now,
            time_observed=now,
            hlc=hlc.now(),
            security={"e2e": False, "bridge_mode": "NONE"},
            provenance=["p"],
            tombstone=None,
            body={"text": "no url here", "format": "plain"},
            rel={"conversation_id": "chat1", "participants": ["+1"]},
            attachments=[{"name": "link.pluginPayloadAttachment", "mime": "text/html", "uri": "p"}],
        )
    )
    conv = list(
        get_conversation(
            "did:person:test", output="objects", group_by_conversation=False, hide_plugin_payload=True
        )
    )
    assert conv[0]["attachments"] == []
    assert conv[1]["attachments"]


def test_handle_normalization():
    assert normalize_handle("+1 (410)925-6693") == "tel:+14109256693"
    assert normalize_handle("User@Example.COM") == "mailto:user@example.com"


def test_list_chats_cli(tmp_path, capsys):
    store = SQLiteEventStore(path=tmp_path / "events.db")
    log = EventLog(store)
    eventlog_module.default_log = log
    hlc = HLC()
    now = datetime.utcnow()
    for i in range(2):
        log.append_event(
            MessageEvent(
                event_id=f"m{i}",
                kind=EventKind.MESSAGE,
                person_did="did:person:test",
                source={"service": "imessage", "id": f"m{i}", "sender": "+1"},
                time_event=now,
                time_observed=now,
                hlc=hlc.now(),
                security={"e2e": False, "bridge_mode": "NONE"},
                provenance=["p"],
                tombstone=None,
                body={"text": "x", "format": "plain"},
                rel={"conversation_id": "room3", "participants": ["+1"]},
                attachments=[],
            )
        )
    unify_cli.main(["--person", "did:person:test", "--list-chats"])
    out = capsys.readouterr().out.splitlines()
    assert any("room3" in line and "2 msgs" in line for line in out)


def test_show_handles_markdown(tmp_path, capsys):
    store = SQLiteEventStore(path=tmp_path / "events.db")
    log = EventLog(store)
    eventlog_module.default_log = log
    hlc = HLC()
    now = datetime.utcnow()
    log.append_event(
        MessageEvent(
            event_id="m1",
            kind=EventKind.MESSAGE,
            person_did="did:person:test",
            source={"service": "imessage", "id": "m1", "sender": "+1410"},
            time_event=now,
            time_observed=now,
            hlc=hlc.now(),
            security={"e2e": False, "bridge_mode": "NONE"},
            provenance=["p"],
            tombstone=None,
            body={"text": "hi", "format": "plain"},
            rel={"conversation_id": "room4", "participants": ["+1410", "me"]},
            attachments=[],
        )
    )
    unify_cli.main(["--person", "did:person:test", "--chat", "room4", "--show-handles"])
    out = capsys.readouterr().out
    assert "tel:+1410" in out
