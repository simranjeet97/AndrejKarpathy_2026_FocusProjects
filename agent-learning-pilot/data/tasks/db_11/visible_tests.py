from solution import process_generator
def test_basic():
    g = (x for x in [1, 2]); assert process_generator(g) == [1, 2]
