# -*- coding: utf-8 -*-
"""
Core export logic for imessage-cli.

- Finds all 1:1 chats for given handles (phone numbers or email addresses), merging SMS/iMessage threads.
- Reads in read-only mode.
- Drops tapbacks (associated_message_type 2000..2006), keeps replies/threads.
- Decodes 'attributedBody' blobs (Sequoia) with a heuristic filter to get human text.
- Lists attachments inline; can optionally copy the files next to the transcript.
"""

import os, sqlite3, datetime, re, pathlib, shutil
from typing import Iterable, List, Dict, Any, Optional

APPLE_EPOCH = 978307200  # seconds from Unix epoch to 2001-01-01 00:00:00
DB_PATH = os.path.expanduser("~/Library/Messages/chat.db")

def _connect_readonly(db_path: str):
    uri = f"file:{db_path}?mode=ro"
    return sqlite3.connect(uri, uri=True, check_same_thread=False)

def _clean_digits(phone: str) -> str:
    return "".join(ch for ch in phone if ch.isdigit())

def _ts_local(apple_ts: int) -> str:
    t = int(apple_ts or 0)
    if t > 1000000000000:  # ns since 2001 epoch
        t //= 1000000000
    return datetime.datetime.fromtimestamp(t + APPLE_EPOCH).strftime("%Y-%m-%d %H:%M")

def _apple_seconds_from_local_date(d: str, end_of_day: bool = False) -> int:
    dt = datetime.datetime.fromisoformat(d)
    if end_of_day:
        dt = dt + datetime.timedelta(days=1)  # exclusive upper bound
    unix = int(dt.timestamp())
    return unix - APPLE_EPOCH

def _attachment_names(conn, message_rowid: int) -> List[str]:
    q = """
      SELECT COALESCE(a.transfer_name, a.filename)
      FROM attachment a
      JOIN message_attachment_join maj ON maj.attachment_id = a.rowid
      WHERE maj.message_id = ?
      ORDER BY a.rowid
    """
    cur = conn.cursor()
    cur.execute(q, (message_rowid,))
    out = []
    for (n,) in cur.fetchall():
        if n:
            out.append(os.path.basename(n))
    return out

def _attachment_files(conn, message_rowid: int) -> List[str]:
    q = """
      SELECT a.filename
      FROM attachment a
      JOIN message_attachment_join maj ON maj.attachment_id = a.rowid
      WHERE maj.message_id = ?
      ORDER BY a.rowid
    """
    cur = conn.cursor()
    cur.execute(q, (message_rowid,))
    return [p for (p,) in cur.fetchall() if p]

def _from_attributed(blob: Optional[bytes]) -> str:
    if not blob:
        return ""
    if isinstance(blob, memoryview):
        blob = blob.tobytes()
    s = blob.decode("utf-8", "ignore")
    s = s.replace("\x00", " ").replace("\uFFFC", " ")  # strip nulls + object-repl char
    s = re.sub(r"(__?kIM|kIM)[A-Za-z0-9_]+", " ", s)
    s = re.sub(r"\bNS[A-Za-z0-9_]+\b", " ", s)
    s = re.sub(r"\bat_\d+_[A-F0-9-]+\b", " ", s)
    s = re.sub(r"com\.apple\.[\w\.-]+|\$\w+", " ", s)
    cands = [t.strip() for t in re.findall(r"[^\x00-\x1f\x7f]{2,}", s)]
    cands = [t for t in cands if any(c.isalpha() for c in t)]
    bad = ("archiver", "NSDictionary", "NSString", "Coder", "root", "MessageAttachment")
    cands = [t for t in cands if not any(b in t for b in bad)]
    return max(cands, key=len) if cands else ""

def _clean_text(t: str) -> str:
    if not t:
        return ""
    t = t.replace("\uFFFC", " ")
    t = re.sub(r"\bstreamtyped\b", "", t, flags=re.I)
    t = re.sub(r"\bat_\d+_[A-F0-9-]+\b", "", t)
    t = re.sub(r"^\s*\+\s*([A-Za-z0-9'&,$#\.\-])?\s*", "", t)  # odd "+A"/"+9"/etc prefixes
    t = re.sub(r"^\s*[A-Za-z]\s+(?=https?://)", "", t)          # stray letter before URL
    t = re.sub(r"\s{2,}", " ", t).strip()
    return t

def _guess_other_label(other_label: Optional[str], handles: Iterable[str]) -> str:
    if other_label:
        return other_label
    first = next(iter(handles))
    if "@" in first:
        return first.split("@", 1)[0]
    d = _clean_digits(first)
    return f"+{d[-10:-7]}-{d[-7:-4]}-{d[-4:]}" if len(d) >= 10 else first

def _find_chat_ids_for_handle(conn, handle: str) -> List[int]:
    cur = conn.cursor()
    if "@" in handle:
        q = """
        SELECT c.rowid
        FROM chat c
        JOIN chat_handle_join chj ON chj.chat_id = c.rowid
        JOIN handle h ON h.rowid = chj.handle_id
        WHERE LOWER(h.id) = LOWER(?)
        GROUP BY c.rowid
        HAVING COUNT(DISTINCT chj.handle_id) = 1
        """
        cur.execute(q, (handle.lower(),))
    else:
        digits = _clean_digits(handle)
        q = """
        SELECT c.rowid
        FROM chat c
        JOIN chat_handle_join chj ON chj.chat_id = c.rowid
        JOIN handle h ON h.rowid = chj.handle_id
        WHERE REPLACE(REPLACE(REPLACE(h.id,'+',''),'-',''),' ','') LIKE ?
        GROUP BY c.rowid
        HAVING COUNT(DISTINCT chj.handle_id) = 1
        """
        cur.execute(q, (f"%{digits}%",))
    return [r[0] for r in cur.fetchall()]

def _find_chat_ids_for_handles(conn, handles: Iterable[str]) -> List[int]:
    ids = set()
    for h in handles:
        ids.update(_find_chat_ids_for_handle(conn, h))
    return sorted(ids)

def _fetch_messages(conn, chat_ids, keep_replies=True, drop_tapbacks=True,
                    since: Optional[str]=None, until: Optional[str]=None):
    if not chat_ids:
        return []
    cur = conn.cursor()
    ph = ",".join("?" * len(chat_ids))
    conds = [f"cmj.chat_id IN ({ph})"]
    params: List[Any] = list(chat_ids)

    if since:
        since_appl = _apple_seconds_from_local_date(since, end_of_day=False)
        conds.append("(CASE WHEN m.date > 1000000000000 THEN m.date/1000000000 ELSE m.date END) >= ?")
        params.append(since_appl)
    if until:
        until_appl = _apple_seconds_from_local_date(until, end_of_day=True)
        conds.append("(CASE WHEN m.date > 1000000000000 THEN m.date/1000000000 ELSE m.date END) < ?")
        params.append(until_appl)

    if drop_tapbacks:
        conds.append("COALESCE(m.associated_message_type,0) NOT IN (2000,2001,2002,2003,2004,2005,2006)")

    where = " AND ".join(conds)
    q = f"""
    SELECT DISTINCT m.rowid, m.date, m.is_from_me, m.text, m.attributedBody, h.id AS handle_id
    FROM message m
    JOIN chat_message_join cmj ON cmj.message_id = m.rowid
    JOIN chat_handle_join chj ON chj.chat_id = cmj.chat_id
    JOIN handle h ON h.rowid = chj.handle_id
    WHERE {where}
    ORDER BY m.date ASC
    """
    cur.execute(q, params)
    return cur.fetchall()

def default_output_path(other_label_or_phone: str, as_txt: bool = False) -> pathlib.Path:
    desk = pathlib.Path.home() / "Desktop"
    suffix = ".txt" if as_txt else ".md"
    date = datetime.date.today().strftime("%Y-%m-%d")
    safe = re.sub(r"[^\w\-\+]+", "_", other_label_or_phone).strip("_")
    return desk / f"{safe}_iMessage_Transcript_{date}{suffix}"

def export_conversation(
    handles: Iterable[str],
    me_label: str = "Me",
    other_label: Optional[str] = None,
    output_path: str = "",
    as_markdown: bool = True,
    preserve_newlines: bool = False,
    since: Optional[str] = None,
    until: Optional[str] = None,
    copy_attachments: bool = False
) -> Dict[str, Any]:
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Messages database not found at {DB_PATH}")
    conn = _connect_readonly(DB_PATH)
    conn.row_factory = sqlite3.Row

    chat_ids = _find_chat_ids_for_handles(conn, handles)
    if not chat_ids:
        raise RuntimeError("No matching 1:1 chat found for those handles.")

    rows = _fetch_messages(conn, chat_ids, keep_replies=True, drop_tapbacks=True,
                           since=since, until=until)

    other_label = _guess_other_label(other_label, handles)
    out_path = pathlib.Path(output_path) if output_path else default_output_path(other_label, as_txt=not as_markdown)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    attachments_dir = None
    if copy_attachments:
        attachments_dir = out_path.with_suffix("").as_posix() + "_attachments"
        pathlib.Path(attachments_dir).mkdir(parents=True, exist_ok=True)

    lines: List[str] = []
    if as_markdown:
        lines.append(f"# {other_label} — iMessage transcript (exported {datetime.date.today():%Y-%m-%d})")
        lines.append("")

    msg_count = 0
    att_count = 0
    current_handle = None

    for m in rows:
        handle_id = m["handle_id"]
        if handle_id != current_handle:
            lines.append(f"--- via {handle_id} ---")
            current_handle = handle_id
        body = m["text"] or _from_attributed(m["attributedBody"]) or ""
        body = _clean_text(body)
        who = me_label if m["is_from_me"] == 1 else other_label
        text = body if preserve_newlines else body.replace("\r", "\n").replace("\n", "↵")

        att_names = _attachment_names(conn, m["rowid"])
        if not text and not att_names:
            continue

        line = f"{_ts_local(m['date'])} — {who}: {text}"
        if att_names:
            line += " [attachments: " + ", ".join(att_names) + "]"
            att_count += len(att_names)

        lines.append(line)
        msg_count += 1

        if copy_attachments:
            for src in _attachment_files(conn, m["rowid"]):
                try:
                    if not src:
                        continue
                    src_path = pathlib.Path(src)
                    if not src_path.is_absolute():
                        src_path = pathlib.Path.home() / "Library/Messages" / src_path
                    if src_path.exists():
                        shutil.copy2(src_path, attachments_dir)
                except Exception:
                    pass

    out_path.write_text("\n".join(lines), encoding="utf-8")

    return {"messages": msg_count, "attachments": att_count, "attachments_dir": attachments_dir}
