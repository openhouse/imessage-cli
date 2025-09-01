from unified.hlc import HLC


def test_hlc_ordering():
    hlc = HLC()
    t1 = hlc.now()
    t2 = hlc.now()
    assert HLC.compare(t1, t2) < 0


def test_hlc_merge():
    a = HLC()
    b = HLC()
    a.now()
    tb1 = b.now()
    a.merge(tb1)
    ta2 = a.now()
    assert HLC.compare(tb1, ta2) < 0
