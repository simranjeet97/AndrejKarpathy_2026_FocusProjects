from solution import dijkstra
def test_basic():
    assert dijkstra({"A": [("B", 1)]}, "A") == {"A": 0, "B": 1}
