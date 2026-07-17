import pytest
from unittest.mock import AsyncMock, patch

from src.agent.nodes.escalation_gate import should_escalate
from src.agent.state import init_state


@pytest.mark.asyncio
async def test_should_escalate_continue() -> None:
    state = init_state(customer_id="cust_1", first_message="hi")
    state["confidence_score"] = 0.95
    state["error_count"] = 0
    state["timeout_budget_remaining"] = 20.0
    state["escalated"] = False

    res = await should_escalate(state)
    assert res == "continue"
    assert state["escalated"] is False


@pytest.mark.asyncio
@patch("src.agent.nodes.escalation_gate.escalate_to_human")
async def test_should_escalate_low_confidence(mock_escalate: AsyncMock) -> None:
    mock_escalate.return_value = {"ticket_id": "tkt_123", "estimated_response_hours": 1.0}
    
    mock_db = AsyncMock()
    mock_redis = AsyncMock()

    state = init_state(customer_id="cust_1", first_message="hi")
    state["confidence_score"] = 0.2  # < 0.4 triggers escalation

    res = await should_escalate(state, db_pool=mock_db, redis_client=mock_redis)
    assert res == "escalate"
    assert state["escalated"] is True
    assert len(state["messages"]) == 2  # user message + human agent notice
    assert "human support agent" in state["messages"][1]["content"]
    mock_escalate.assert_called_once()


@pytest.mark.asyncio
@patch("src.agent.nodes.escalation_gate.escalate_to_human")
async def test_should_escalate_high_errors(mock_escalate: AsyncMock) -> None:
    mock_escalate.return_value = {"ticket_id": "tkt_123", "estimated_response_hours": 2.0}
    
    mock_db = AsyncMock()
    mock_redis = AsyncMock()

    state = init_state(customer_id="cust_1", first_message="hi")
    state["error_count"] = 2  # >= 2 triggers escalation

    res = await should_escalate(state, db_pool=mock_db, redis_client=mock_redis)
    assert res == "escalate"
    assert state["escalated"] is True
    mock_escalate.assert_called_once()


@pytest.mark.asyncio
@patch("src.agent.nodes.escalation_gate.escalate_to_human")
async def test_should_escalate_low_budget(mock_escalate: AsyncMock) -> None:
    mock_escalate.return_value = {"ticket_id": "tkt_123", "estimated_response_hours": 0.5}
    
    mock_db = AsyncMock()
    mock_redis = AsyncMock()

    state = init_state(customer_id="cust_1", first_message="hi")
    state["timeout_budget_remaining"] = 1.5  # < 2.0 triggers escalation

    res = await should_escalate(state, db_pool=mock_db, redis_client=mock_redis)
    assert res == "escalate"
    assert state["escalated"] is True
    mock_escalate.assert_called_once()
