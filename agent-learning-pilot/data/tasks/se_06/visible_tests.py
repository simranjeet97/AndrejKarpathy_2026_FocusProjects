from solution import PluginRegistry
def test_basic():
    pr = PluginRegistry(); pr.register("p1", 10); assert pr.get("p1") == 10
