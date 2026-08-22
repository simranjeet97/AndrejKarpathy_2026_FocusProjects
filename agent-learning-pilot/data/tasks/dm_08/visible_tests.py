from solution import running_average
def test_basic():
    assert running_average([10, 20, 30]) == [10.0, 15.0, 20.0]
