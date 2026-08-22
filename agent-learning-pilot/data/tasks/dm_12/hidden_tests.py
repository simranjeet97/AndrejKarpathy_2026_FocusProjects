from solution import recursive_dict_diff
def test_hidden():
    assert recursive_dict_diff({}, {}) == {}
