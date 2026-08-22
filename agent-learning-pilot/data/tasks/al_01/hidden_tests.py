from solution import binary_search
def test_hidden():
    assert binary_search([], 3) == -1
    assert binary_search([1, 3, 5], 4) == -1
