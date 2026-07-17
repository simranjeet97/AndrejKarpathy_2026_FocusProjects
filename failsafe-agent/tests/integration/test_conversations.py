import asyncio
import time
import pytest
from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from httpx import AsyncClient
import stripe

from src.main import app
from src.agent.state import Intent
from src.resilience.circuit_breaker import CircuitOpenError
from src.observability.metrics import RETRIES_TOTAL, CIRCUIT_BREAKER_STATE


@pytest.fixture
def mock_infrastructure() -> Generator:
    # Set up mock Postgres Pool and Redis Client
    mock_db = MagicMock()
    mock_conn = AsyncMock()
    mock_db.acquire.return_value.__aenter__.return_value = mock_conn
    
    mock_redis = MagicMock()
    mock_pipe = AsyncMock()
    mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
    mock_pipe.__aexit__ = AsyncMock(return_value=False)
    # Simulate sliding window execution outputs: [zrem, zadd, zcard (count=1), zrange, expire]
    mock_pipe.execute = AsyncMock(return_value=[0, 1, 1, [(b"ts", time.time())], True])
    mock_redis.pipeline = MagicMock(return_value=mock_pipe)
    
    redis_store = {}
    async def mock_get(key: str) -> bytes:
        return redis_store.get(key)
    async def mock_set(key: str, val: bytes, **kwargs) -> None:
        redis_store[key] = val
    
    mock_redis.get = AsyncMock(side_effect=mock_get)
    mock_redis.set = AsyncMock(side_effect=mock_set)
    mock_redis.xadd = AsyncMock(return_value="1-0")
    
    # Store old app state
    old_db = getattr(app.state, "db_pool", None)
    old_redis = getattr(app.state, "redis_client", None)
    
    app.state.db_pool = mock_db
    app.state.redis_client = mock_redis
    
    # Mocking standard startup checks inside endpoints
    mock_conn.fetchval.return_value = 0  # 0 existing refunds (for guardrail check)
    
    yield mock_db, mock_redis, mock_conn
    
    app.state.db_pool = old_db
    app.state.redis_client = old_redis


@pytest.mark.asyncio
@patch("src.agent.nodes.classifier.call_anthropic_api")
@patch("src.agent.nodes.main_agent.call_with_fallback")
@patch("stripe.Charge.retrieve")
@patch("stripe.Refund.create")
async def test_happy_path_refund(
    mock_refund_create: MagicMock,
    mock_charge_retrieve: MagicMock,
    mock_llm_fallback: AsyncMock,
    mock_classifier_api: AsyncMock,
    mock_infrastructure: Any,
) -> None:
    mock_db, mock_redis, mock_conn = mock_infrastructure

    # 1. Mock Classifier and LLM outputs
    mock_classifier_api.return_value = {
        "content": [{"type": "text", "text": "REFUND_REQUEST"}]
    }

    # Simulate Main Agent tool call and then completion
    mock_llm_fallback.side_effect = [
        # Turn 1: Main Agent decides to check eligibility and issue refund
        {
            "content": [
                {
                    "type": "tool_use",
                    "id": "tool_issue",
                    "name": "issue_refund",
                    "input": {"charge_id": "ch_123", "amount_cents": 5000, "reason": "DEFECTIVE"}
                }
            ],
            "stop_reason": "tool_use"
        },
        # Turn 2: Main Agent responds with success text
        {
            "content": [{"type": "text", "text": "Refund processed successfully."}],
            "stop_reason": "end_turn"
        }
    ]

    # 2. Mock Stripe charge to be eligible (succeeded, created 2 days ago)
    mock_charge_retrieve.return_value = {
        "id": "ch_123",
        "status": "succeeded",
        "amount": 5000,
        "created": time.time() - (2 * 86400)
    }
    mock_refund_create.return_value = {
        "id": "re_123",
        "status": "succeeded"
    }

    async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/conversations",
            json={"customer_id": "cust_01", "message": "I want a refund for ch_123"},
            headers={"X-Customer-ID": "cust_01"}
        )

    assert response.status_code == 201
    res_data = response.json()
    assert res_data["resolved"] is True
    assert res_data["escalated"] is False
    assert "processed" in res_data["response"]

    # Verify audit event logged for start, tool, etc.
    assert mock_conn.execute.call_count > 0


@pytest.mark.asyncio
@patch("src.agent.nodes.classifier.call_anthropic_api")
async def test_escalation_on_low_confidence(
    mock_classifier_api: AsyncMock,
    mock_infrastructure: Any,
) -> None:
    mock_db, mock_redis, mock_conn = mock_infrastructure

    # Mock classifier to return UNCLEAR which sets confidence_score to 0.5
    mock_classifier_api.return_value = {
        "content": [{"type": "text", "text": "UNCLEAR"}]
    }

    # Verify that the escalation gate kicks in because confidence is low or intent is UNCLEAR
    # Note: run_agent/escalation_gate will call raw_escalate_to_human
    async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/conversations",
            json={"customer_id": "cust_01", "message": "unclear request"},
            headers={"X-Customer-ID": "cust_01"}
        )

    assert response.status_code == 201
    res_data = response.json()
    assert res_data["resolved"] is False
    assert res_data["escalated"] is True
    assert res_data["ticket_id"] is not None


@pytest.mark.asyncio
@patch("src.agent.nodes.classifier.call_anthropic_api")
@patch("src.agent.nodes.main_agent.call_with_fallback")
@patch("stripe.Charge.retrieve")
@patch("stripe.Refund.create")
async def test_retry_on_stripe_failure(
    mock_refund_create: MagicMock,
    mock_charge_retrieve: MagicMock,
    mock_llm_fallback: AsyncMock,
    mock_classifier_api: AsyncMock,
    mock_infrastructure: Any,
) -> None:
    mock_db, mock_redis, mock_conn = mock_infrastructure

    # Reset Prometheus counter before testing
    RETRIES_TOTAL.clear()

    mock_classifier_api.return_value = {
        "content": [{"type": "text", "text": "REFUND_REQUEST"}]
    }

    mock_llm_fallback.side_effect = [
        {
            "content": [
                {
                    "type": "tool_use",
                    "id": "tool_issue",
                    "name": "issue_refund",
                    "input": {"charge_id": "ch_123", "amount_cents": 5000, "reason": "DEFECTIVE"}
                }
            ],
            "stop_reason": "tool_use"
        },
        {
            "content": [{"type": "text", "text": "Refund processed."}],
            "stop_reason": "end_turn"
        }
    ]

    mock_charge_retrieve.return_value = {
        "id": "ch_123",
        "status": "succeeded",
        "amount": 5000,
        "created": time.time()
    }

    # Stripe Refund fails twice with stripe.error.APIError then succeeds
    mock_refund_create.side_effect = [
        stripe.error.APIError("Stripe API transient error", http_status=500),
        stripe.error.APIError("Stripe API transient error", http_status=500),
        {"id": "re_123", "status": "succeeded"}
    ]

    async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/conversations",
            json={"customer_id": "cust_01", "message": "Refund please"},
            headers={"X-Customer-ID": "cust_01"}
        )

    assert response.status_code == 201
    res_data = response.json()
    assert res_data["resolved"] is True
    
    # Assert retries counter was incremented
    # Since it failed twice and succeeded on the 3rd attempt, there should be 2 retry records
    # Verify via metrics list or internal counts
    # (Checking the total sum of metrics)
    retry_count = sum(val.value for val in RETRIES_TOTAL.collect()[0].samples)
    assert retry_count >= 2


@pytest.mark.asyncio
@patch("src.agent.nodes.classifier.call_anthropic_api")
@patch("src.agent.nodes.main_agent.call_with_fallback")
@patch("stripe.Charge.retrieve")
@patch("stripe.Refund.create")
async def test_circuit_breaker_trip(
    mock_refund_create: MagicMock,
    mock_charge_retrieve: MagicMock,
    mock_llm_fallback: AsyncMock,
    mock_classifier_api: AsyncMock,
    mock_infrastructure: Any,
) -> None:
    mock_db, mock_redis, mock_conn = mock_infrastructure

    # Reset circuit breaker gauge
    CIRCUIT_BREAKER_STATE.clear()

    mock_classifier_api.return_value = {
        "content": [{"type": "text", "text": "REFUND_REQUEST"}]
    }

    call_counts = {"total": 0}
    async def side_effect_llm(messages, **kwargs):
        if len(messages) == 1:
            call_counts["total"] += 1
            charge_id = f"ch_{call_counts['total']}"
            return {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tool_issue",
                        "name": "issue_refund",
                        "input": {"charge_id": charge_id, "amount_cents": 5000, "reason": "DEFECTIVE"}
                    }
                ],
                "stop_reason": "tool_use"
            }
        return {
            "content": [{"type": "text", "text": "Refund failed."}],
            "stop_reason": "end_turn"
        }
    mock_llm_fallback.side_effect = side_effect_llm

    mock_charge_retrieve.return_value = {
        "id": "ch_123",
        "status": "succeeded",
        "amount": 5000,
        "created": time.time()
    }

    # Make Stripe Refund fail continuously (raises error)
    mock_refund_create.side_effect = stripe.error.APIError("Stripe API outage", http_status=500)

    # Triggering multiple conversation requests to force 5 circuit breaker failures
    # Or mock circuit breaker class state directly. Since the threshold is 5 failures:
    for _ in range(5):
        try:
            async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
                await ac.post(
                    "/conversations",
                    json={"customer_id": "cust_01", "message": "Refund request"},
                    headers={"X-Customer-ID": "cust_01"}
                )
        except Exception:
            pass

    # Verify circuit breaker enters OPEN state
    # (check metric value)
    cb_states = [sample.value for sample in CIRCUIT_BREAKER_STATE.collect()[0].samples]
    # At least one service (llm or stripe refund) should record open state (value 1.0)
    assert 1.0 in cb_states
