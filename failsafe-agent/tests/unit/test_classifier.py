import pytest
from unittest.mock import AsyncMock, patch

from src.agent.nodes.classifier import classify_intent
from src.agent.state import init_state, Intent


@pytest.mark.asyncio
@patch("src.agent.nodes.classifier.call_anthropic_api")
async def test_classify_intent_success(mock_api: AsyncMock) -> None:
    mock_api.return_value = {
        "content": [{"type": "text", "text": "REFUND_REQUEST"}]
    }
    
    state = init_state(customer_id="cust_1", first_message="I want my money back")
    updated_state = await classify_intent(state)
    
    assert updated_state["intent"] == Intent.REFUND_REQUEST.value
    assert updated_state["confidence_score"] == 1.0  # remains unchanged
    assert updated_state["timeout_budget_remaining"] < 28.0
    assert updated_state["error_count"] == 0


@pytest.mark.asyncio
@patch("src.agent.nodes.classifier.call_anthropic_api")
async def test_classify_intent_unclear(mock_api: AsyncMock) -> None:
    mock_api.return_value = {
        "content": [{"type": "text", "text": "UNCLEAR"}]
    }
    
    state = init_state(customer_id="cust_1", first_message="what is the meaning of life")
    updated_state = await classify_intent(state)
    
    assert updated_state["intent"] == Intent.UNCLEAR.value
    assert updated_state["confidence_score"] == 0.3
    assert updated_state["error_count"] == 0


@pytest.mark.asyncio
@patch("src.agent.nodes.classifier.call_anthropic_api")
async def test_classify_intent_failure(mock_api: AsyncMock) -> None:
    # API raises connection error
    mock_api.side_effect = Exception("API connection timed out")
    
    state = init_state(customer_id="cust_1", first_message="Hello")
    updated_state = await classify_intent(state)
    
    assert updated_state["intent"] == Intent.UNCLEAR.value
    assert updated_state["confidence_score"] == 0.3
    assert updated_state["error_count"] == 1
