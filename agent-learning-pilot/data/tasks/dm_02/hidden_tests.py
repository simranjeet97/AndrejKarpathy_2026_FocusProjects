from solution import group_by_key
def test_hidden():
    assert group_by_key([], len) == {}
    assert group_by_key(None, len) == {}
