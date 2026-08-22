from solution import parse_int_safe
def test_basic():
    assert parse_int_safe("123") == 123
    assert parse_int_safe("abc") == None
