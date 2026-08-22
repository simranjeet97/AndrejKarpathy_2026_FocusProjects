from solution import compute_stats
def test_basic():
    assert compute_stats([1, 2, 3]) == {"count": 3, "sum": 6, "mean": 2.0}
