import logging
import sqlite3
from pathlib import Path

from imessage_exporter.identity.resolve import resolve_person
from imessage_exporter.collectors import imessage as imessage_collector


def build_chat_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    c = conn.cursor()
    c.executescript(
        """
        CREATE TABLE handle (ROWID INTEGER PRIMARY KEY, id TEXT);
        CREATE TABLE chat (ROWID INTEGER PRIMARY KEY, guid TEXT);
        CREATE TABLE chat_handle_join (chat_id INTEGER, handle_id INTEGER);
        CREATE TABLE message (
            ROWID INTEGER PRIMARY KEY,
            guid TEXT,
            date INTEGER,
            text TEXT,
            is_from_me INTEGER,
            handle_id INTEGER,
            associated_message_guid TEXT,
            associated_message_type INTEGER
        );
        CREATE TABLE chat_message_join (chat_id INTEGER, message_id INTEGER);
        CREATE TABLE message_attachment_join (message_id INTEGER, attachment_id INTEGER);
        CREATE TABLE attachment (ROWID INTEGER PRIMARY KEY, filename TEXT, mime_type TEXT, transfer_name TEXT);
        """
    )
    c.executemany("INSERT INTO handle (ROWID,id) VALUES (?,?)", [(1, '4155551212'), (2, '4155551313')])
    c.execute("INSERT INTO chat (ROWID,guid) VALUES (1,'chat1')")
    c.executemany("INSERT INTO chat_handle_join (chat_id,handle_id) VALUES (1,?)", [(1,), (2,)])
    msgs = [
        (1, 'm1', 1000, 'hi', 1, None, None, None),
        (2, 'm2', 2000, 'hey', 0, 1, None, None),
        (3, 'm3', 3000, 'group', 1, None, None, None),
        (4, 'm4', 4000, 'other', 0, 2, None, None),
        (5, 'm5', 5000, None, 0, 1, 'm3', 2000),
        (6, 'm6', 6000, 'reply', 0, 1, 'm1', 1000),
        (7, 'm7', 7000, 'att', 0, 1, None, None),
    ]
    c.executemany("INSERT INTO message VALUES (?,?,?,?,?,?,?,?)", msgs)
    for mid in range(1,8):
        c.execute("INSERT INTO chat_message_join VALUES (1,?)", (mid,))
    c.execute("INSERT INTO attachment VALUES (1,'/nope/path.txt','text/plain','path.txt')")
    c.execute("INSERT INTO message_attachment_join VALUES (7,1)")
    conn.commit()
    conn.close()


def collect_events(tmp_path, scope="direct", **kwargs):
    db_path = tmp_path / "chat.db"
    build_chat_db(db_path)
    person = resolve_person("Test", phones=["+14155551212"])
    return list(imessage_collector.collect(person, db_path, scope=scope, **kwargs))


def test_direct_scope_filters_group_messages(tmp_path):
    events = collect_events(tmp_path, scope="direct")
    ids = [e.id for e in events]
    assert 'm4' not in ids
    assert 'm3' in ids


def test_replies_and_reactions_linked_not_duplicated(tmp_path):
    events = collect_events(tmp_path, scope="contextual")
    by_id = {e.id: e for e in events}
    assert by_id['m5'].association.target_id == 'm3'
    assert by_id['m6'].association.target_id == 'm1'
    assert len(events) == len({e.id for e in events})


def test_attachments_listing_and_copy_errors_logged(tmp_path, caplog):
    caplog.set_level(logging.WARNING)
    events = collect_events(tmp_path, copy_attachments=True, attachments_dir=tmp_path)
    att_event = next(e for e in events if e.id == 'm7')
    assert att_event.attachments and att_event.attachments[0].path.endswith('path.txt')
    assert any('attachment copy failed' in r.message for r in caplog.records)
