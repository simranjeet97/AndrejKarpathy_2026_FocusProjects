from solution import compute_stats
def test_hidden():
    assert compute_stats([]) == {"count": 0, "sum": 0, "mean": 0}
