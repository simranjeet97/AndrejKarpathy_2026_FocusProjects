from solution import pivot_table
def test_hidden():
    assert pivot_table([], "r", "c", "v") == {}
