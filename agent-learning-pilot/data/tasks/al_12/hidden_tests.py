from solution import UnionFind
def test_hidden():
    uf = UnionFind(3); assert uf.find(0) != uf.find(2)
