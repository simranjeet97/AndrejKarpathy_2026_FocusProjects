from solution import safe_increment
def test_basic():
    assert safe_increment({"c": 0}, 5) == {"c": 5}
