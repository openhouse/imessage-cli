from __future__ import annotations

import csv
import json
import os
import platform
import subprocess
from pathlib import Path
from typing import Dict, Iterable, Optional

PEOPLE_PATH = Path.home() / ".imx/unified/people.json"

def _load_people() -> Dict[str, Dict[str, object]]:
    if PEOPLE_PATH.exists():
        return json.loads(PEOPLE_PATH.read_text(encoding="utf-8"))
    return {}

def load_vcf(path: Path) -> Dict[str, str]:
    """Very small vCard parser for TEL/EMAIL → FN mapping (no third-party deps)."""
    mapping: Dict[str, str] = {}
    if not path.exists():
        return mapping
    name = None
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line.upper().startswith("FN:"):
            name = line.split(":", 1)[1].strip()
        elif line.upper().startswith("TEL") or line.upper().startswith("EMAIL"):
            if ":" in line:
                handle = line.split(":", 1)[1].strip()
                if handle and name:
                    mapping[handle] = name
    return mapping

def load_csv(path: Path) -> Dict[str, str]:
    """CSV with columns: name, handle (phone/email)."""
    mapping: Dict[str, str] = {}
    if not path.exists():
        return mapping
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            handle = (row.get("handle") or "").strip()
            name = (row.get("name") or "").strip()
            if handle and name:
                mapping[handle] = name
    return mapping

def query_macos_contacts(handle: str) -> Optional[str]:
    """Best-effort Apple Contacts lookup via AppleScript (Darwin only)."""
    if platform.system() != "Darwin":
        return None
    script = f'''
    on hasValueWithSubstring(theList, theSub)
        repeat with v in theList
            if (v as text) contains theSub then return true
        end repeat
        return false
    end hasValueWithSubstring
    tell application "Contacts"
        set matches to {{}}
        repeat with p in people
            set allVals to (value of phones of p) & (value of emails of p)
            if my hasValueWithSubstring(allVals, "{handle}") then
                copy name of p to end of matches
            end if
        end repeat
        if (count of matches) > 0 then return item 1 of matches
        return ""
    end tell
    '''
    try:
        out = subprocess.check_output(["osascript", "-e", script], text=True).strip()
        return out or None
    except Exception:
        return None

def build_resolver(contacts_vcf: Optional[Path] = None, contacts_csv: Optional[Path] = None):
    people = _load_people()
    by_handle: Dict[str, str] = {}

    # From people.json VCs
    for did, info in people.items():
        label = (info.get("label") or "") if isinstance(info, dict) else ""
        for vc_id in (info.get("vc_ids") or []):
            # wallet.load_vc not imported to avoid circular; rely on label for now
            pass
        # Also allow raw handles list if present
        for h in (info.get("handles") or []):
            if isinstance(h, str) and label:
                by_handle[h] = label

    # External sources
    if contacts_vcf:
        by_handle.update(load_vcf(contacts_vcf))
    if contacts_csv:
        by_handle.update(load_csv(contacts_csv))

    def resolve(handle: Optional[str], fallback_display: Optional[str] = None) -> str:
        if not handle:
            return fallback_display or "Unknown"
        # exact
        if handle in by_handle:
            return by_handle[handle]
        # heuristic: strip formatting for phone numbers
        digits = "".join(ch for ch in handle if ch.isdigit() or ch == "+")
        for k, v in by_handle.items():
            kd = "".join(ch for ch in k if ch.isdigit() or ch == "+")
            if kd and kd == digits:
                return v
        # macOS contacts last
        mac = query_macos_contacts(handle)
        if mac:
            return mac
        return fallback_display or handle

    return resolve
