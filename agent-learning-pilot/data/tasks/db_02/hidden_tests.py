from solution import find_max
def test_hidden():
    assert find_max([]) == None
    assert find_max([-3, -1, -5]) == -1
