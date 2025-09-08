from __future__ import annotations
from collections import defaultdict
from typing import Dict, List, Optional, Sequence, Tuple

from ..storage_sqlite import SQLiteEventStore
from ..eventlog import iter_events
from ..identity import contacts
from ..identity.contacts import expand_handles, normalize_handle_for_matching


def db_persons() -> List[str]:
    store = SQLiteEventStore()
    cur = store.conn.cursor()
    try:
        cur.execute("SELECT DISTINCT person_did FROM events")
        return [r[0] for r in cur.fetchall() if r and r[0]]
    except Exception:
        return []


def summarize_persons() -> List[Dict[str, object]]:
    store = SQLiteEventStore()
    cur = store.conn.cursor()
    counts: Dict[str, int] = {}
    spans: Dict[str, Tuple[str, str]] = {}
    services: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    try:
        cur.execute("SELECT person_did, COUNT(*) FROM events GROUP BY 1")
        counts = {did: int(n) for did, n in cur.fetchall()}
    except Exception:
        pass

    try:
        cur.execute(
            "SELECT person_did, MIN(time_event), MAX(time_event) FROM events GROUP BY 1"
        )
        spans = {did: (str(s or "?"), str(e or "?")) for did, s, e in cur.fetchall()}
    except Exception:
        pass

    try:
        cur.execute(
            "SELECT person_did, json_extract(source,'$.service'), COUNT(*) FROM events GROUP BY 1,2"
        )
        for did, svc, c in cur.fetchall():
            if did:
                services[str(did)][str(svc or "?")] += int(c or 0)
    except Exception:
        pass

    labels = {}
    try:
        from ..identity import did as did_module  # lazy

        reg = did_module._load_registry()  # type: ignore[attr-defined]
        labels = {d: (info.get("label") or "") for d, info in (reg or {}).items()}
    except Exception:
        pass

    rows: List[Dict[str, object]] = []
    for did, n in sorted(counts.items(), key=lambda kv: kv[1], reverse=True):
        start, end = spans.get(did, ("?", "?"))
        svcs = services.get(did, {})
        total = sum(svcs.values()) or 1
        top = sorted(svcs.items(), key=lambda kv: kv[1], reverse=True)[:3]
        top_s = (
            ", ".join(f"{name}({int(c*100/total)}%)" for name, c in top) if top else ""
        )
        rows.append(
            {
                "person_did": did,
                "label": labels.get(did, ""),
                "events": n,
                "start": start,
                "end": end,
                "services": top_s,
            }
        )
    return rows


def print_persons_summary() -> None:
    rows = summarize_persons()
    if not rows:
        print("No persons found in the event log.")
        return
    print("Persons discovered in the event log:")
    for r in rows:
        label = f' [{r["label"]}]' if r.get("label") else ""
        print(
            f"- {r['person_did']}{label} · {r['events']} events · {r['start']} → {r['end']} · services: {r['services']}"
        )
    print("\nRe-run with:  imx unify --person '<person_did>'  …")


def _handle_variants(norm_handles: Sequence[str]) -> List[str]:
    v: set[str] = set()
    for h in norm_handles:
        if h.startswith("mailto:"):
            addr = h.split(":", 1)[1]
            v.update({addr, addr.lower(), h, h.lower()})
        elif h.startswith("tel:"):
            num = h.split(":", 1)[1]
            digits = "".join(ch for ch in num if ch.isdigit())
            v.update({h, num, "+" + digits, digits})
        else:
            v.update({h, h.lower()})
    return sorted(v)


def guess_person_from_voice(seed: str) -> Tuple[Optional[str], Dict[str, int]]:
    display, handles, _ = expand_handles(seed, contacts.DEFAULT_VCF, contacts.DEFAULT_CSV)
    norm = sorted(handles)
    variants = _handle_variants(norm)
    evidence: Dict[str, int] = defaultdict(int)
    store = SQLiteEventStore()
    cur = store.conn.cursor()

    if variants:
        placeholders = ",".join(["?"] * len(variants))
        lower_variants = [v.lower() for v in variants]
        # Prefer SQL with JSON1
        try:
            cur.execute(
                f"""SELECT person_did, COUNT(*)
                    FROM events
                    WHERE LOWER(COALESCE(json_extract(source,'$.sender'), '')) IN ({placeholders})
                    GROUP BY 1""",
                lower_variants,
            )
            for did, c in cur.fetchall():
                if did and c:
                    evidence[str(did)] += int(c)
        except Exception:
            pass
        try:
            cur.execute(
                f"""SELECT e.person_did, COUNT(*)
                    FROM events AS e, json_each(e.rel, '$.participants') AS p
                    WHERE LOWER(COALESCE(p.value, '')) IN ({placeholders})
                    GROUP BY 1""",
                lower_variants,
            )
            for did, c in cur.fetchall():
                if did and c:
                    evidence[str(did)] += int(c)
        except Exception:
            pass

    # Fallback: light Python scan if SQL didn’t help
    if not evidence:
        persons = db_persons()
        target_norm = {normalize_handle_for_matching(v) for v in variants} | set(norm)
        for did in persons:
            for ev in iter_events(did):
                if ev.kind.name != "MESSAGE":
                    continue
                snd = ev.source.get("sender") or ""
                if normalize_handle_for_matching(snd) in target_norm:
                    evidence[did] += 1
                    break

    winners = [did for did, c in evidence.items() if c > 0]
    if len(winners) == 1:
        return winners[0], dict(evidence)
    return None, dict(evidence)
