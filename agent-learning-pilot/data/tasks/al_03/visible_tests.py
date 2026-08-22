from solution import merge_intervals
def test_basic():
    assert merge_intervals([(1, 3), (2, 6)]) == [(1, 6)]
