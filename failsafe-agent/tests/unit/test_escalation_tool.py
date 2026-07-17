import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.tools.escalation_tool import escalate_to_human


@pytest.mark.asyncio
async def test_escalate_to_human_urgent() -> None:
    # Set up mock dependencies
    mock_conn = AsyncMock()
    mock_db_pool = MagicMock()
    mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

    mock_redis = AsyncMock()

    res = await escalate_to_human(
        conversation_id="conv_123",
        customer_id="cust_99",
        reason="Refusing fallback options",
        confidence_score=0.15,  # < 0.3 -> urgent, 0.5 hours
        conversation_history=[{"role": "user", "content": "help"}],
        tool_call_log=[{"tool": "refund"}],
        db_pool=mock_db_pool,
        redis_client=mock_redis,
    )

    # 1. Assert result fields
    assert res["estimated_response_hours"] == 0.5
    assert res["ticket_id"].startswith("tkt_")

    # 2. Verify Postgres execution parameters
    mock_conn.execute.assert_called_once()
    sql_args = mock_conn.execute.call_args[0]
    
    assert "INSERT INTO tickets" in sql_args[0]
    assert sql_args[1] == res["ticket_id"]  # id
    assert sql_args[2] == "conv_123"        # conversation_id
    assert sql_args[3] == "urgent"           # priority
    
    # Check context JSON content
    context_data = json.loads(sql_args[4])
    assert context_data["customer_id"] == "cust_99"
    assert context_data["confidence_score"] == 0.15
    assert context_data["reason"] == "Refusing fallback options"
    assert "agent_model_used" in context_data

    # 3. Verify Redis publishers
    mock_redis.xadd.assert_called_once_with(
        "escalations",
        {"ticket_id": res["ticket_id"], "priority": "urgent"}
    )
    mock_redis.set.assert_called_once_with(
        f"escalated:conv_123", "true"
    )


@pytest.mark.asyncio
async def test_escalate_to_human_high_priority() -> None:
    mock_conn = AsyncMock()
    mock_db_pool = MagicMock()
    mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn
    mock_redis = AsyncMock()

    res = await escalate_to_human(
        conversation_id="conv_456",
        customer_id="cust_88",
        reason="Stripe connection timed out",
        confidence_score=0.45,  # 0.3 <= score < 0.6 -> high, 1.0 hours
        conversation_history=[],
        tool_call_log=[],
        db_pool=mock_db_pool,
        redis_client=mock_redis,
    )

    assert res["estimated_response_hours"] == 1.0
    mock_redis.xadd.assert_called_once_with(
        "escalations",
        {"ticket_id": res["ticket_id"], "priority": "high"}
    )
