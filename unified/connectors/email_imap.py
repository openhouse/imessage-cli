from __future__ import annotations

import email
from email import policy
from email.utils import parsedate_to_datetime
from pathlib import Path
from datetime import datetime

from ..eventlog import EventLog
from ..hlc import HLC
from ..schema import EventKind, MessageEvent
from ..trust import BridgeMode


def ingest_eml_dir(dir_path: Path, person_did: str, log: EventLog, hlc: HLC) -> None:
    for path in sorted(dir_path.glob("*.eml")):
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            msg = email.message_from_file(f, policy=policy.default)
        body = msg.get_body(preferencelist=("plain",))
        text = body.get_content() if body else ""
        event = MessageEvent(
            event_id=msg.get("Message-ID", path.name),
            kind=EventKind.MESSAGE,
            person_did=person_did,
            source={
                "service": "email",
                "id": msg.get("Message-ID", path.name),
                "sender": "other",
            },
            time_event=(
                parsedate_to_datetime(msg.get("Date"))
                if msg.get("Date")
                else datetime.utcnow()
            ),
            time_observed=datetime.utcnow(),
            hlc=hlc.now(),
            security={"e2e": False, "bridge_mode": BridgeMode.NONE.value},
            provenance=[f"eml {path.name}"],
            tombstone=None,
            body={"text": text, "format": "plain"},
            rel={
                "in_reply_to": msg.get("In-Reply-To"),
                "message_id": msg.get("Message-ID"),
            },
            attachments=[],
        )
        log.append_event(event)
