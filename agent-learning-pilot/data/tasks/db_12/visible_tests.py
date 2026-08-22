from solution import make_multipliers
def test_basic():
    fns = make_multipliers(); assert [f(2) for f in fns] == [0, 2, 4]
