from solution import copy_matrix
def test_basic():
    m = [[1]]; c = copy_matrix(m); c[0][0] = 2; assert m[0][0] == 1
