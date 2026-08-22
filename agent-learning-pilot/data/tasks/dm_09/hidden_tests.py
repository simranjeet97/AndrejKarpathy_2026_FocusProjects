from solution import missing_value_imputation
def test_hidden():
    assert missing_value_imputation([]) == []
    assert missing_value_imputation([None, None]) == [0, 0]
