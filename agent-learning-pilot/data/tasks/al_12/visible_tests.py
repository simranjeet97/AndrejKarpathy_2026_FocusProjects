from solution import UnionFind
def test_basic():
    uf = UnionFind(3); uf.union(0, 1); assert uf.find(0) == uf.find(1)
