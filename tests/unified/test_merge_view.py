from datetime import datetime, timedelta

from unified.eventlog import EventLog
from unified import eventlog as eventlog_module
from unified.hlc import HLC
from unified.schema import (
    DeleteEvent,
    EditEvent,
    EventKind,
    MessageEvent,
    ReactionEvent,
)
from unified.storage_sqlite import SQLiteEventStore
from unified.trust import BridgeMode
from unified.views.conversation import get_conversation


def test_merge_view(tmp_path):
    store = SQLiteEventStore(path=tmp_path / "events.db")
    log = EventLog(store)
    eventlog_module.default_log = log
    hlc = HLC()
    person = "did:person:test"
    now = datetime.utcnow()

    m1 = MessageEvent(
        event_id="m1",
        kind=EventKind.MESSAGE,
        person_did=person,
        source={"service": "imessage", "id": "m1", "sender": "other"},
        time_event=now,
        time_observed=now,
        hlc=hlc.now(),
        security={"e2e": False, "bridge_mode": BridgeMode.ON_DEVICE.value},
        provenance=["imessage row 1"],
        tombstone=None,
        body={"text": "hi", "format": "plain"},
        rel={},
        attachments=[],
    )
    log.append_event(m1)

    m2 = MessageEvent(
        event_id="m2",
        kind=EventKind.MESSAGE,
        person_did=person,
        source={"service": "email", "id": "m2", "sender": "me"},
        time_event=now + timedelta(seconds=1),
        time_observed=now + timedelta(seconds=1),
        hlc=hlc.now(),
        security={"e2e": False, "bridge_mode": BridgeMode.NONE.value},
        provenance=["eml a.eml"],
        tombstone=None,
        body={"text": "hello", "format": "plain"},
        rel={},
        attachments=[],
    )
    log.append_event(m2)

    edit = EditEvent(
        event_id="e1",
        kind=EventKind.EDIT,
        person_did=person,
        source={"service": "email", "id": "e1", "sender": "me"},
        time_event=now + timedelta(seconds=2),
        time_observed=now + timedelta(seconds=2),
        hlc=hlc.now(),
        security={"e2e": False, "bridge_mode": BridgeMode.NONE.value},
        provenance=["eml edit"],
        tombstone=None,
        target_event_id="m2",
        patch={"text": "hello edited"},
    )
    log.append_event(edit)

    react = ReactionEvent(
        event_id="r1",
        kind=EventKind.REACTION,
        person_did=person,
        source={"service": "imessage", "id": "r1", "sender": "me"},
        time_event=now + timedelta(seconds=3),
        time_observed=now + timedelta(seconds=3),
        hlc=hlc.now(),
        security={"e2e": False, "bridge_mode": BridgeMode.ON_DEVICE.value},
        provenance=["imessage reaction"],
        tombstone=None,
        target_event_id="m1",
        reaction="👍",
    )
    log.append_event(react)

    delete = DeleteEvent(
        event_id="d1",
        kind=EventKind.DELETE,
        person_did=person,
        source={"service": "imessage", "id": "d1", "sender": "other"},
        time_event=now + timedelta(seconds=4),
        time_observed=now + timedelta(seconds=4),
        hlc=hlc.now(),
        security={"e2e": False, "bridge_mode": BridgeMode.ON_DEVICE.value},
        provenance=["imessage delete"],
        tombstone={"reason": "deleted"},
        target_event_id="m1",
    )
    log.append_event(delete)

    conv = list(get_conversation(person))
    assert len(conv) == 2
    assert conv[0]["tombstone"]["reason"] == "deleted"
    assert conv[0]["reactions"] == ["👍"]
    assert conv[1]["text"] == "hello edited"


def test_stable_ordering_same_time(tmp_path):
    store = SQLiteEventStore(path=tmp_path / "events.db")
    log = EventLog(store)
    eventlog_module.default_log = log
    hlc = HLC()
    person = "did:person:test"
    now = datetime.utcnow()

    first = MessageEvent(
        event_id="a",
        kind=EventKind.MESSAGE,
        person_did=person,
        source={"service": "imessage", "id": "a", "sender": "other"},
        time_event=now,
        time_observed=now,
        hlc=hlc.now(),
        security={"e2e": False, "bridge_mode": BridgeMode.ON_DEVICE.value},
        provenance=["p1"],
        tombstone=None,
        body={"text": "first", "format": "plain"},
        rel={},
        attachments=[],
    )
    log.append_event(first)

    second = MessageEvent(
        event_id="b",
        kind=EventKind.MESSAGE,
        person_did=person,
        source={"service": "imessage", "id": "b", "sender": "other"},
        time_event=now,
        time_observed=now,
        hlc=hlc.now(),
        security={"e2e": False, "bridge_mode": BridgeMode.ON_DEVICE.value},
        provenance=["p2"],
        tombstone=None,
        body={"text": "second", "format": "plain"},
        rel={},
        attachments=[],
    )
    log.append_event(second)

    conv = list(get_conversation(person))
    assert [c["text"] for c in conv] == ["first", "second"]
