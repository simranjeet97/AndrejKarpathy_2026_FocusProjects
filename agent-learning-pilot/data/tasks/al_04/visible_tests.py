from solution import LRUCache
def test_basic():
    c = LRUCache(2); c.put(1,1); assert c.get(1) == 1
