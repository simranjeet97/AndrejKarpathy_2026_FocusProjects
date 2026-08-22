from solution import get_config
def test_hidden():
    assert isinstance(get_config("NONEXISTENT"), dict)
