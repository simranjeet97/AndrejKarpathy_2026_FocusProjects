from solution import bfs_shortest_path
def test_basic():
    assert bfs_shortest_path({"A": ["B"], "B": []}, "A", "B") == ["A", "B"]
