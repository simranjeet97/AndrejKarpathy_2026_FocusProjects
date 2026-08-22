from solution import pivot_table
def test_basic():
    assert pivot_table([{"r": "a", "c": "x", "v": 10}], "r", "c", "v") == {"a": {"x": 10}}
