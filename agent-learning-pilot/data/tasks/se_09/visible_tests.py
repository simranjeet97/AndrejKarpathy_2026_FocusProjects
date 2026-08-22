from solution import repeat
def test_basic():
    @repeat(2)
    def foo(): return 1
    assert foo() == 1
