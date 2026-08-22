from solution import RequestBuilder
def test_hidden():
    assert RequestBuilder().build() == {}
