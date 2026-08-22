from solution import serialize, deserialize
def test_basic():
    assert deserialize(serialize({"a": 1})) == {"a": 1}
