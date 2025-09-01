from unified.normalize.time import apple_ts_to_dt_local


def test_apple_ts_normalization_units():
    base = 600
    dt_s = apple_ts_to_dt_local(base)
    dt_us = apple_ts_to_dt_local(base * 1_000_000)
    dt_ns = apple_ts_to_dt_local(base * 1_000_000_000)
    assert dt_s == dt_us == dt_ns
