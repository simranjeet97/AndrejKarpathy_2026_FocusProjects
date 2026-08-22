from solution import extract_emails
def test_hidden():
    assert extract_emails("invalid email") == []
