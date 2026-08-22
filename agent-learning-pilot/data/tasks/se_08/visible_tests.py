from solution import RequestBuilder
def test_basic():
    b = RequestBuilder().set_url("http://test.com").build(); assert b.get("url") == "http://test.com"
