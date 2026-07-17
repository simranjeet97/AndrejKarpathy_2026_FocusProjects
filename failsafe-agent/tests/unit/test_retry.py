from unittest.mock import AsyncMock, patch
import pytest
import httpx
from freezegun import freeze_time

from src.resilience.retry import with_retry, RateLimitError


@pytest.mark.asyncio
async def test_retry_success_first_attempt() -> None:
    mock_func = AsyncMock(return_value="success")
    decorated = with_retry(max_attempts=3)(mock_func)
    
    res = await decorated()
    assert res == "success"
    assert mock_func.call_count == 1


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_retry_success_after_failure(mock_sleep: AsyncMock) -> None:
    calls = []
    
    @with_retry(max_attempts=3, base_delay=1.0)
    async def dummy() -> str:
        calls.append(1)
        if len(calls) < 2:
            raise RateLimitError("Rate limited")
        return "success"
        
    res = await dummy()
    assert res == "success"
    assert len(calls) == 2
    assert mock_sleep.call_count == 1
    
    # The first retry sleep backoff limit is base_delay * 2**0 = 1.0
    sleep_delay = mock_sleep.call_args[0][0]
    assert 0 <= sleep_delay <= 1.0


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_retry_max_attempts_exhausted(mock_sleep: AsyncMock) -> None:
    mock_func = AsyncMock(side_effect=httpx.TimeoutException("Timeout error"))
    decorated = with_retry(max_attempts=3, base_delay=1.0)(mock_func)
    
    with pytest.raises(httpx.TimeoutException):
        await decorated()
        
    assert mock_func.call_count == 3
    assert mock_sleep.call_count == 2
    
    # Asserting delay bounds (attempt 1 -> 2**0 * 1 = 1s limit; attempt 2 -> 2**1 * 1 = 2s limit)
    delay_1 = mock_sleep.call_args_list[0][0][0]
    delay_2 = mock_sleep.call_args_list[1][0][0]
    assert 0 <= delay_1 <= 1.0
    assert 0 <= delay_2 <= 2.0


@freeze_time("2026-07-17T12:00:00Z")
@pytest.mark.asyncio
async def test_retry_with_freezegun() -> None:
    # Basic freezegun verification demonstrating time freeze structure
    mock_func = AsyncMock(return_value="done")
    decorated = with_retry(max_attempts=2)(mock_func)
    res = await decorated()
    assert res == "done"
