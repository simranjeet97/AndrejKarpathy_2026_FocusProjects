from solution import schema_validation
def test_basic():
    assert schema_validation({"a": 1}, {"a": int}) == True
