from solution import config_parser
def test_basic():
    assert config_parser(["a=1", "b=2"]) == {"a": "1", "b": "2"}
