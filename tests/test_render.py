import sqlite3
from pathlib import Path

from imessage_exporter.identity.resolve import resolve_person
from imessage_exporter.collectors import imessage as imessage_collector
from imessage_exporter.collectors import calls as calls_collector
from imessage_exporter.merge.merge import merge_events
from imessage_exporter.render import markdown as markdown_render
from imessage_exporter.render import jsonl as jsonl_render

from .test_collectors import build_chat_db


def build_calls_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    c = conn.cursor()
    c.execute("CREATE TABLE call (rowid INTEGER PRIMARY KEY, address TEXT, date INTEGER, duration INTEGER, flags INTEGER)")
    c.execute("INSERT INTO call VALUES (1,'+14155551212',8000,60,2)")
    conn.commit()
    conn.close()


def test_jsonl_stream_and_markdown_render_ordering(tmp_path):
    chat_db = tmp_path / 'chat.db'
    build_chat_db(chat_db)
    calls_db = tmp_path / 'calls.db'
    build_calls_db(calls_db)
    person = resolve_person('Test', phones=['+14155551212'])
    im_events = list(imessage_collector.collect(person, chat_db, scope='contextual'))
    call_events = list(calls_collector.collect(person, calls_db))
    merged = merge_events(im_events, call_events)
    ts_list = [e.ts for e in merged]
    assert ts_list == sorted(ts_list)
    md_path = tmp_path / 'timeline.md'
    jsonl_path = tmp_path / 'timeline.jsonl'
    with md_path.open('w', encoding='utf-8') as fh:
        markdown_render.render(merged, fh)
    with jsonl_path.open('w', encoding='utf-8') as fh:
        jsonl_render.render(merged, fh)
    md_lines = md_path.read_text().splitlines()
    jsonl_lines = jsonl_path.read_text().splitlines()
    assert len(md_lines) == len(jsonl_lines)
    first_id = merged[0].id
    assert first_id in md_lines[0]
