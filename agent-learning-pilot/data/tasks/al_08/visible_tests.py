from solution import Trie
def test_basic():
    t = Trie(); t.insert("cat"); assert "cat" in t.search("ca")
