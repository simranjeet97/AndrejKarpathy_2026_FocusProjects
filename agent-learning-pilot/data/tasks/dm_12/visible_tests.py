from solution import recursive_dict_diff
def test_basic():
    assert recursive_dict_diff({"a": 1}, {"a": 2}) == {"a": (1, 2)}
