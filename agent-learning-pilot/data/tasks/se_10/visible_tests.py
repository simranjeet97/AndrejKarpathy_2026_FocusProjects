from solution import ManagedResource
def test_basic():
    with ManagedResource("r") as res: pass
