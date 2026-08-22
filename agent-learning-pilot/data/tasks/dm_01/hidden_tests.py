from solution import filter_by_predicate
def test_hidden():
    assert filter_by_predicate([], lambda x: True) == []
    assert filter_by_predicate(None, lambda x: True) == []
    assert filter_by_predicate([1, 2], lambda x: False) == []
