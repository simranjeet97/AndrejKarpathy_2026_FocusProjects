from solution import task_scheduler
def test_basic():
    assert task_scheduler(["A","A","A","B","B","B"], 2) == 8
