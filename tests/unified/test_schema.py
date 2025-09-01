from datetime import datetime

from unified.schema import EventKind, MessageEvent, event_from_dict
from unified.trust import BridgeMode


def test_roundtrip_message():
    now = datetime.utcnow()
    event = MessageEvent(
        event_id="e1",
        kind=EventKind.MESSAGE,
        person_did="did:person:test",
        source={"service": "imessage", "id": "1", "sender": "other"},
        time_event=now,
        time_observed=now,
        hlc="0:0:local",
        security={"e2e": False, "bridge_mode": BridgeMode.ON_DEVICE.value},
        provenance=["row 1"],
        tombstone=None,
        body={"text": "hi", "format": "plain"},
        rel={},
        attachments=[],
    )
    data = event.to_dict()
    restored = event_from_dict(data)
    assert restored == event
