from solution import deduplicate_records
def test_hidden():
    assert deduplicate_records([]) == []
    assert deduplicate_records([{"id": 1}, {"id": 1}], key_fn=lambda x: x["id"]) == [{"id": 1}]
