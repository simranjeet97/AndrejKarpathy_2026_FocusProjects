from solution import parse_csv_manual
def test_basic():
    assert parse_csv_manual("a,b
1,2") == [{"a": "1", "b": "2"}]
