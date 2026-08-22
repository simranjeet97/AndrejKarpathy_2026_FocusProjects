from solution import group_by_key
def test_basic():
    assert group_by_key(["a", "bb", "c"], len) == {1: ["a", "c"], 2: ["bb"]}
