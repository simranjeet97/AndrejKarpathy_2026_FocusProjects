from solution import EventDispatcher
def test_hidden():
    ed = EventDispatcher(); ed.dispatch("unhandled", 1)
