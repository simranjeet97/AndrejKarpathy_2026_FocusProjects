from solution import merge_sorted_streams
def test_basic():
    assert merge_sorted_streams([1, 3], [2, 4]) == [1, 2, 3, 4]
