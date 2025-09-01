from imessage_exporter.normalize.time import apple_ts_to_dt_local
from imessage_exporter.identity.resolve import resolve_person


def test_timestamp_detection():
    base_seconds = 600
    dt_s = apple_ts_to_dt_local(base_seconds)
    dt_us = apple_ts_to_dt_local(base_seconds * 1_000_000)
    dt_ns = apple_ts_to_dt_local(base_seconds * 1_000_000_000)
    assert dt_s == dt_us == dt_ns


def test_identity_normalization():
    p = resolve_person("Test", phones=["+1 (415) 555-1212"], emails=["Name@Example.Com"])
    assert p.handles_norm == ["4155551212", "name@example.com"]
    assert p.raw_to_norm["Name@Example.Com"] == "name@example.com"
