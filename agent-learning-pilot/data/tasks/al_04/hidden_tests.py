from solution import LRUCache
def test_hidden():
    c = LRUCache(1); c.put(1,1); c.put(2,2); assert c.get(1) == -1
