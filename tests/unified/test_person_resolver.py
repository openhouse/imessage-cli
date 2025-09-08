from datetime import datetime
from unified.eventlog import EventLog
from unified import eventlog as eventlog_module
from unified.schema import EventKind, MessageEvent
from unified.storage_sqlite import SQLiteEventStore
from unified.cli import person_resolver
from unified.cli.person_resolver import db_persons, summarize_persons, guess_person_from_voice
from unified.identity import contacts


def _msg(event_id, did, who, svc="imessage", cid="room", text="hi", t=None):
    t = t or datetime(2021, 1, 1, 12, 0, 0)
    return MessageEvent(
        event_id=event_id,
        kind=EventKind.MESSAGE,
        person_did=did,
        source={"service": svc, "id": event_id, "sender": who, "route": svc},
        time_event=t,
        time_observed=t,
        hlc="0:0:0",
        security={"e2e": False, "bridge_mode": "NONE"},
        provenance=[svc],
        tombstone=None,
        body={"text": text, "format": "plain"},
        rel={"conversation_id": cid, "participants": [who, "me"]},
        attachments=[],
    )


def test_guess_unique(tmp_path, monkeypatch):
    # set people.json so expand_handles knows email <-> phone if needed
    people = tmp_path / "people.json"
    people.write_text(
        '{"L":{"label":"L","handles":["mailto:l@example.com","tel:+155501"]}}'
    )
    monkeypatch.setattr(contacts, "PEOPLE_PATH", people)

    store = SQLiteEventStore(path=tmp_path / "events.db")
    log = EventLog(store)
    eventlog_module.default_log = log
    monkeypatch.setattr(person_resolver, "SQLiteEventStore", lambda: store)
    log.append_event(_msg("a", "did:one", "l@example.com", svc="email"))
    log.append_event(_msg("b", "did:two", "other@example.com", svc="email"))

    monkeypatch.setenv("IMX_IGNORE", "1")  # noop, present to show pattern

    did, evidence = guess_person_from_voice("l@example.com")
    assert did == "did:one"
    assert evidence["did:one"] >= 1


def test_summarize(tmp_path, monkeypatch):
    store = SQLiteEventStore(path=tmp_path / "events.db")
    log = EventLog(store)
    eventlog_module.default_log = log
    monkeypatch.setattr(person_resolver, "SQLiteEventStore", lambda: store)
    log.append_event(_msg("a", "did:one", "me"))
    log.append_event(_msg("b", "did:one", "me"))
    log.append_event(_msg("c", "did:two", "me"))
    rows = summarize_persons()
    assert rows[0]["person_did"] in {"did:one", "did:two"}
