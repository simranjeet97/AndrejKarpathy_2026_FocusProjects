from solution import migrate_schema
def test_basic():
    assert migrate_schema({"v": 1, "name": "a"}, 2) == {"v": 2, "name": "a", "active": True}
