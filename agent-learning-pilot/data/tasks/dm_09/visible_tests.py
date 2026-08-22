from solution import missing_value_imputation
def test_basic():
    assert missing_value_imputation([1, None, 3]) == [1, 2.0, 3]
