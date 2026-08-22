from solution import deduplicate_records
def test_basic():
    assert deduplicate_records([1, 2, 2, 3]) == [1, 2, 3]
