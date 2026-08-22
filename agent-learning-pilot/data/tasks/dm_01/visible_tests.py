from solution import filter_by_predicate
def test_basic():
    assert filter_by_predicate([1, 2, 3, 4], lambda x: x > 2) == [3, 4]
