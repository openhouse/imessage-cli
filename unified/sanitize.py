from __future__ import annotations

import re

# Remove leading stray char before http(s), fix ttps://, strip WHttpURL/ trailer.
def clean_urls(text: str) -> str:
    if not text:
        return text
    t = text.replace("WHttpURL/", "")
    # remove stray leading char like 'K' before https://
    t = re.sub(r'\b([A-Za-z\*])(?=https?://)', '', t)
    # fix ttps:// or Ttps://
    t = re.sub(r'\b[tT]tps://', 'https://', t)
    return t


def has_url(text: str) -> bool:
    return bool(re.search(r'https?://\S+', text or ""))


# Basic handle normalizer used for display
PHONE_RE = re.compile(r'\D')


def normalize_handle(handle: str) -> str:
    h = (handle or "").strip()
    if not h:
        return ""
    if '@' in h or h.lower().startswith('mailto:'):
        addr = h.split(':', 1)[1] if h.lower().startswith('mailto:') else h
        return f"mailto:{addr.lower()}"
    # phone numbers
    plus = '+' if h.startswith('+') else ''
    digits = PHONE_RE.sub('', h)
    if plus:
        digits = '+' + digits
    if not digits.startswith('+'):
        if len(digits) == 10:
            digits = '+1' + digits
        else:
            digits = '+' + digits
    return f"tel:{digits}"
