from solution import PluginRegistry
def test_hidden():
    pr = PluginRegistry(); assert pr.get("missing") == None
