from solution import migrate_schema
def test_hidden():
    assert migrate_schema({}, 2) == {"v": 2, "active": True}
