from solution import retry_with_backoff
def test_basic():
    assert retry_with_backoff(lambda: 42) == 42
