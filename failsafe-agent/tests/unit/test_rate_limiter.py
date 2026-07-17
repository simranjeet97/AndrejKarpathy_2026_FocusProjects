import datetime
import time
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.policy.rate_limiter import check_rate_limit, RateLimitResult


@pytest.mark.asyncio
async def test_check_rate_limit_allowed() -> None:
    mock_redis = MagicMock()
    
    # Simulate pipeline execution results:
    # [zremrangebyscore_result, zadd_result, zcard_result, zrange_result, expire_result]
    now = time.time()
    mock_pipe = AsyncMock()
    mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
    mock_pipe.__aexit__ = AsyncMock(return_value=False)
    mock_pipe.execute = AsyncMock(return_value=[
        0,           # zremrangebyscore: removed 0 old elements
        1,           # zadd: added 1 element
        3,           # zcard: 3 current calls (below max 10)
        [(b"ts", now)],  # zrange: oldest element
        True,        # expire: key TTL set
    ])
    mock_redis.pipeline = MagicMock(return_value=mock_pipe)

    res = await check_rate_limit(
        customer_id="cust_1",
        action="conversations",
        max_calls=10,
        window_seconds=3600,
        redis_client=mock_redis,
    )

    assert isinstance(res, RateLimitResult)
    assert res.allowed is True
    assert res.remaining == 7  # max 10 - count 3
    assert isinstance(res.reset_at, datetime.datetime)


@pytest.mark.asyncio
async def test_check_rate_limit_exceeded() -> None:
    mock_redis = MagicMock()
    now = time.time()

    mock_pipe = AsyncMock()
    mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
    mock_pipe.__aexit__ = AsyncMock(return_value=False)
    mock_pipe.execute = AsyncMock(return_value=[
        0,
        1,
        11,           # 11 calls, exceeds max 10
        [(b"ts", now)],
        True,
    ])
    mock_redis.pipeline = MagicMock(return_value=mock_pipe)

    res = await check_rate_limit(
        customer_id="cust_1",
        action="conversations",
        max_calls=10,
        window_seconds=3600,
        redis_client=mock_redis,
    )

    assert res.allowed is False
    assert res.remaining == 0


@pytest.mark.asyncio
async def test_check_rate_limit_refund_attempts() -> None:
    mock_redis = MagicMock()
    now = time.time()

    mock_pipe = AsyncMock()
    mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
    mock_pipe.__aexit__ = AsyncMock(return_value=False)
    mock_pipe.execute = AsyncMock(return_value=[0, 1, 2, [(b"ts", now)], True])
    mock_redis.pipeline = MagicMock(return_value=mock_pipe)

    # 3 refunds per day (86400s window)
    res = await check_rate_limit(
        customer_id="cust_1",
        action="refund_attempts",
        max_calls=3,
        window_seconds=86400,
        redis_client=mock_redis,
    )

    assert res.allowed is True
    assert res.remaining == 1  # max 3 - count 2
