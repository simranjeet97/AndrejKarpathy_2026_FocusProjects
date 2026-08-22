from solution import validate_user
def test_hidden():
    assert len(validate_user({})) > 0
    assert len(validate_user(None)) > 0
