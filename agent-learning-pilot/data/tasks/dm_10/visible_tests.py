from solution import time_series_resample
def test_basic():
    assert time_series_resample([1, 2, 3, 4], 2) == [1.5, 3.5]
