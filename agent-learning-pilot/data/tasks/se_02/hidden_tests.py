from solution import config_parser
def test_hidden():
    assert config_parser([]) == {}
