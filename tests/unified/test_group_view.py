from datetime import datetime, timedelta
from unified.eventlog import EventLog
from unified import eventlog as eventlog_module
from unified.hlc import HLC
from unified.schema import EventKind, MessageEvent
from unified.storage_sqlite import SQLiteEventStore
from unified.views.conversation import get_conversation


def _msg(event_id, who, chat, text, t, hlc, service="imessage", route="imessage:sms"):
    return MessageEvent(
        event_id=event_id,
        kind=EventKind.MESSAGE,
        person_did="did:person:test",
        source={"service": service, "id": event_id, "sender": who, "route": route, "chat_guid": chat},
        time_event=t,
        time_observed=t,
        hlc=hlc.now(),
        security={"e2e": False, "bridge_mode": "NONE"},
        provenance=[f"{service} row"],
        tombstone=None,
        body={"text": text, "format": "plain"},
        rel={"conversation_id": f"{service}:chat:{chat}", "participants": [who, "me"]},
        attachments=[],
    )


def test_group_and_via_collapse(tmp_path):
    store = SQLiteEventStore(path=tmp_path / "events.db")
    log = EventLog(store)
    eventlog_module.default_log = log
    hlc = HLC()
    now = datetime.utcnow()

    # Same text/time from same sender via two routes -> collapse
    log.append_event(_msg("a1", "+1410", "CHAT1", "Hello", now, hlc, service="imessage", route="imessage:sms"))
    log.append_event(
        _msg("a2", "+1410", "CHAT1", "Hello", now + timedelta(seconds=30), hlc, service="imessage", route="imessage:imessage")
    )

    conv = list(
        get_conversation(
            "did:person:test",
            output="objects",
            group_by_conversation=True,
            via_collapse=True,
            resolve_display=lambda h, _: h,
        )
    )
    # Expect a header + one message
    assert conv[0]["kind"] == "header"
    msg = conv[1]
    assert msg["text"] == "Hello"
    assert set(msg["via"]) == {"imessage:sms", "imessage:imessage"}
    assert msg["who"] == "+1410"
