from solution import parse_csv_manual
def test_hidden():
    assert parse_csv_manual("") == []
    assert parse_csv_manual(None) == []
