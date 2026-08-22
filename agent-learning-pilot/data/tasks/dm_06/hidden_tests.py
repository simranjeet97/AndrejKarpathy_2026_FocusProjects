from solution import merge_sorted_streams
def test_hidden():
    assert merge_sorted_streams([], [1]) == [1]
    assert merge_sorted_streams([], []) == []
