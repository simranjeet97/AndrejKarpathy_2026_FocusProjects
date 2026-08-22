from solution import EventDispatcher
def test_basic():
    ed = EventDispatcher(); res = []; ed.subscribe("e", lambda p: res.append(p)); ed.dispatch("e", 1); assert res == [1]
