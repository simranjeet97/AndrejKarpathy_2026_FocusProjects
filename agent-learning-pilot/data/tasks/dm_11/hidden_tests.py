from solution import schema_validation
def test_hidden():
    assert schema_validation({"a": "x"}, {"a": int}) == False
