from solution import bfs_shortest_path
def test_hidden():
    assert bfs_shortest_path({"A": []}, "A", "B") == []
