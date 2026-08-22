from solution import get_config
def test_basic():
    import os; os.environ["APP_HOST"] = "localhost"; assert get_config()["host"] == "localhost"
