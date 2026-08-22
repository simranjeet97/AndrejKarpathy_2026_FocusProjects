from solution import sort_by_field
def test_basic():
    assert sort_by_field([{"age": 10}, {"age": 2}], "age") == [{"age": 2}, {"age": 10}]
