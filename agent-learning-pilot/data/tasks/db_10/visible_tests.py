from solution import extract_emails
def test_basic():
    assert extract_emails("test@example.com") == ["test@example.com"]
