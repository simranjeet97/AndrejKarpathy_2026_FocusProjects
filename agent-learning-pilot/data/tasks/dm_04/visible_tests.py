from solution import nested_json_flatten
def test_basic():
    assert nested_json_flatten({"a": {"b": 1}}) == {"a.b": 1}
