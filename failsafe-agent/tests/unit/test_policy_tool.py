import pytest
from src.tools.policy_tool import PolicyStore


def test_policy_store_load_and_get() -> None:
    store = PolicyStore()
    assert len(store.policies) >= 5
    
    # Test valid ID retrieval
    policy = store.get_policy("policy_refund_window")
    assert policy is not None
    assert policy["title"] == "Refund Window and Timeline Policy"
    assert policy["category"] == "Billing"
    
    # Test invalid ID retrieval
    assert store.get_policy("non_existent") is None


@pytest.mark.asyncio
async def test_policy_store_search_relevance() -> None:
    store = PolicyStore()
    
    # Search for refund related policies
    results = await store.search_policy("I want a refund for my charge", top_k=2)
    assert len(results) > 0
    # The top result should be the refund window policy
    assert results[0]["id"] == "policy_refund_window"
    assert results[0]["score"] > 0.0


@pytest.mark.asyncio
async def test_policy_store_search_no_match() -> None:
    store = PolicyStore()
    
    # Search for something entirely unrelated
    results = await store.search_policy("unrelated gibberish query here", top_k=2)
    assert len(results) == 0
