"""Handle normalization utilities."""
from __future__ import annotations

import re
from typing import Optional


_EMAIL_RE = re.compile(r"^[^@]+@[^@]+$")


def norm_email(s: str) -> str:
    return s.strip().lower()


def digits_only(s: str) -> str:
    return re.sub(r"\D", "", s)


def norm_phone_last10(s: str) -> str:
    digits = digits_only(s)
    return digits[-10:]


def is_email(s: str) -> bool:
    return bool(_EMAIL_RE.match(s.strip()))


def handles_equiv(a: str, b: str) -> bool:
    if is_email(a) and is_email(b):
        return norm_email(a) == norm_email(b)
    return norm_phone_last10(a) == norm_phone_last10(b)


def normalize_handle(s: str) -> str:
    return norm_email(s) if is_email(s) else norm_phone_last10(s)
