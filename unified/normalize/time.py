from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Union

APPLE_EPOCH = datetime(2001, 1, 1, tzinfo=timezone.utc)


def apple_ts_to_dt_local(raw: Union[int, float, str, None]) -> datetime:
    """Convert an Apple epoch timestamp to a timezone-aware datetime.

    ``raw`` may be in seconds, microseconds or nanoseconds since the
    Apple epoch (2001-01-01 UTC). The unit is inferred from divisibility.
    ``None`` is treated as ``0`` for safety.
    """
    value = 0 if raw is None else int(float(raw))
    if value % 1_000_000_000 == 0:
        seconds = value / 1_000_000_000
    elif value % 1_000_000 == 0:
        seconds = value / 1_000_000
    else:
        seconds = value
    dt_utc = APPLE_EPOCH + timedelta(seconds=seconds)
    return dt_utc.astimezone()
