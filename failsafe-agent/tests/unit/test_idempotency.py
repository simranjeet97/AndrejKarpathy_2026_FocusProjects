import pytest
from unittest.mock import AsyncMock
from typing import Any
import uuid

from src.resilience.idempotency import idempotent


class StripeRefundError(Exception):
    pass


@pytest.mark.asyncio
async def test_idempotency_stripe_refund() -> None:
    mock_redis = AsyncMock()
    
    # Simple in-memory mock database for Redis client mock
    db_store = {}
    
    async def mock_get(key: str) -> bytes:
        return db_store.get(key)
        
    async def mock_set(key: str, val: bytes, ex: int = None) -> None:
        db_store[key] = val
        
    mock_redis.get.side_effect = mock_get
    mock_redis.set.side_effect = mock_set

    # Key generation function
    def refund_key_fn(charge_id: str, amount: int, **kwargs: Any) -> str:
        return f"refund:{charge_id}:{amount}"

    call_count = 0

    @idempotent(key_fn=refund_key_fn)
    async def stripe_refund(charge_id: str, amount: int, redis_client: Any = None) -> dict:
        nonlocal call_count
        call_count += 1
        if amount <= 0:
            raise StripeRefundError("Amount must be positive")
        return {"refund_id": f"ref_{uuid.uuid4().hex[:8]}", "amount": amount}

    # 1. First refund call (cache miss -> execute)
    res1 = await stripe_refund(charge_id="ch_123", amount=100, redis_client=mock_redis)
    assert res1["amount"] == 100
    assert call_count == 1

    # 2. Second refund call (cache hit -> return cached response)
    res2 = await stripe_refund(charge_id="ch_123", amount=100, redis_client=mock_redis)
    assert res2 == res1
    assert call_count == 1

    # 3. Third refund call with different charge (cache miss -> execute)
    res3 = await stripe_refund(charge_id="ch_456", amount=100, redis_client=mock_redis)
    assert res3 != res1
    assert call_count == 2

    # 4. Fourth call triggering exception (cache miss -> execute and cache exception)
    with pytest.raises(StripeRefundError):
        await stripe_refund(charge_id="ch_invalid", amount=-50, redis_client=mock_redis)
    assert call_count == 3

    # 5. Fifth call (cache hit on exception -> re-raise cached exception without executing)
    with pytest.raises(StripeRefundError):
        await stripe_refund(charge_id="ch_invalid", amount=-50, redis_client=mock_redis)
    assert call_count == 3
