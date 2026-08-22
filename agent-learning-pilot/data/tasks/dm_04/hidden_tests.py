from solution import nested_json_flatten
def test_hidden():
    assert nested_json_flatten({}) == {}
    assert nested_json_flatten({"a": 1}) == {"a": 1}
