from solution import validate_user
def test_basic():
    assert validate_user({"name": "Alice", "age": 30}) == []
