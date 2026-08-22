from solution import process_generator
def test_hidden():
    assert process_generator(iter([])) == []
