import pytest
from unittest.mock import AsyncMock, patch
import httpx

from src.resilience.fallback_llm import call_with_fallback, SafeResponse, call_anthropic_api
from src.config import settings


@pytest.mark.asyncio
@patch("src.resilience.fallback_llm.call_anthropic_api")
async def test_fallback_llm_primary_success(mock_api: AsyncMock) -> None:
    mock_api.return_value = {"content": [{"type": "text", "text": "hello"}], "model": "primary"}
    
    # Mocking Redis to prevent real connection attempts during tests
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    
    res = await call_with_fallback(
        messages=[{"role": "user", "content": "hi"}],
        redis_client=mock_redis
    )
    
    assert res["model"] == "primary"
    assert mock_api.call_count == 1
    mock_api.assert_called_with(
        model=settings.PRIMARY_MODEL,
        messages=[{"role": "user", "content": "hi"}],
        tools=None,
        system_prompt=None,
    )


@pytest.mark.asyncio
@patch("src.resilience.fallback_llm.call_anthropic_api")
async def test_fallback_llm_fallback_success(mock_api: AsyncMock) -> None:
    # First call (primary) raises error, second call (fallback) succeeds
    mock_api.side_effect = [
        httpx.ConnectError("Primary offline"),
        {"content": [{"type": "text", "text": "fallback response"}], "model": "fallback"}
    ]
    
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    
    res = await call_with_fallback(
        messages=[{"role": "user", "content": "hi"}],
        redis_client=mock_redis
    )
    
    assert res["model"] == "fallback"
    assert mock_api.call_count == 2


@pytest.mark.asyncio
@patch("src.resilience.fallback_llm.call_anthropic_api")
async def test_fallback_llm_both_fail_escalates(mock_api: AsyncMock) -> None:
    # Both primary and fallback calls raise errors
    mock_api.side_effect = [
        httpx.ConnectError("Primary offline"),
        httpx.ConnectError("Fallback offline")
    ]
    
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    
    res = await call_with_fallback(
        messages=[{"role": "user", "content": "hi"}],
        redis_client=mock_redis
    )
    
    assert isinstance(res, SafeResponse)
    assert res.escalate is True
    assert "human agent" in res.message
    assert mock_api.call_count == 2
