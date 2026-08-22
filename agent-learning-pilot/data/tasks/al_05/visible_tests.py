from solution import topological_sort
def test_basic():
    assert topological_sort({"A": ["B"], "B": []}) in [["A", "B"]]
