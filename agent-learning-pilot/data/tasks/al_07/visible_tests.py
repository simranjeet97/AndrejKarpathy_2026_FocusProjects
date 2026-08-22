from solution import sliding_window_max
def test_basic():
    assert sliding_window_max([1, 3, -1, 3, 5, 3, 6, 7], 3) == [3, 3, 5, 5, 6, 7]
