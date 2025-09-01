from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from . import wallet
from .vc import create_vc

PEOPLE_PATH = Path.home() / ".imx/unified/people.json"


def _load_registry() -> Dict[str, Dict[str, object]]:
    if PEOPLE_PATH.exists():
        with PEOPLE_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_registry(reg: Dict[str, Dict[str, object]]) -> None:
    PEOPLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PEOPLE_PATH.open("w", encoding="utf-8") as f:
        json.dump(reg, f, indent=2)


def new_person_did() -> str:
    return f"did:person:{uuid.uuid4()}"


def resolve_handles_to_person(handles: List[str]) -> str:
    reg = _load_registry()
    # try to match existing VCs
    for did, info in reg.items():
        for vc_id in info.get("vc_ids", []):
            vc = wallet.load_vc(vc_id)
            for h in vc.get("claims", {}).get("handles", []):
                if h.get("value") in handles:
                    return did
    # create new person and VC
    did = new_person_did()
    vc = create_vc(did, handles, [f"manual-confirmation:{datetime.now().date()}"])
    vc_id = wallet.store_vc(vc)
    reg[did] = {"label": handles[0], "vc_ids": [vc_id]}
    _save_registry(reg)
    return did
