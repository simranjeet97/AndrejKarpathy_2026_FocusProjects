from solution import safe_increment
def test_hidden():
    assert safe_increment({}, 1) == {"c": 1}
