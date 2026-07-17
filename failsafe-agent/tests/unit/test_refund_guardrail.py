import pytest
from unittest.mock import AsyncMock, MagicMock
import time

from src.policy.refund_guardrail import validate_refund, GuardrailViolationError


@pytest.mark.asyncio
async def test_guardrail_invalid_reason() -> None:
    mock_db = MagicMock()
    
    with pytest.raises(GuardrailViolationError) as exc_info:
        await validate_refund(
            customer_id="cust_1",
            charge_id="ch_1",
            amount_cents=1000,
            reason="INVALID_REASON",  # not in allowed list
            db_pool=mock_db
        )
        
    assert "Invalid refund reason" in str(exc_info.value)


@pytest.mark.asyncio
async def test_guardrail_amount_too_high() -> None:
    mock_db = MagicMock()
    mock_charge = {"amount": 5000, "created": time.time()}

    with pytest.raises(GuardrailViolationError) as exc_info:
        await validate_refund(
            customer_id="cust_1",
            charge_id="ch_1",
            amount_cents=6000,  # exceeds original 5000
            reason="DEFECTIVE",
            db_pool=mock_db,
            stripe_charge_mock=mock_charge
        )
        
    assert "must be positive and <= original charge" in str(exc_info.value)


@pytest.mark.asyncio
async def test_guardrail_changed_mind_expired() -> None:
    mock_db = MagicMock()
    # Purchase made 10 days ago (10 * 86400 seconds)
    ten_days_ago = time.time() - (10 * 86400)
    mock_charge = {"amount": 5000, "created": ten_days_ago}

    with pytest.raises(GuardrailViolationError) as exc_info:
        await validate_refund(
            customer_id="cust_1",
            charge_id="ch_1",
            amount_cents=2000,
            reason="CHANGED_MIND",  # > 7 days expired
            db_pool=mock_db,
            stripe_charge_mock=mock_charge
        )
        
    assert "CHANGED_MIND refunds are only allowed within 7 days" in str(exc_info.value)


@pytest.mark.asyncio
async def test_guardrail_exceeds_rolling_limit() -> None:
    # Set up DB connection mock returning 3 existing refunds
    mock_conn = AsyncMock()
    mock_conn.fetchval.return_value = 3  # already has 3 refunds in last 30 days
    mock_db = MagicMock()
    mock_db.acquire.return_value.__aenter__.return_value = mock_conn

    mock_charge = {"amount": 5000, "created": time.time()}

    with pytest.raises(GuardrailViolationError) as exc_info:
        await validate_refund(
            customer_id="cust_1",
            charge_id="ch_1",
            amount_cents=2000,
            reason="DEFECTIVE",
            db_pool=mock_db,
            stripe_charge_mock=mock_charge
        )
        
    assert "already received 3 refunds" in str(exc_info.value)


@pytest.mark.asyncio
async def test_guardrail_success() -> None:
    mock_conn = AsyncMock()
    mock_conn.fetchval.return_value = 1  # only 1 refund in last 30 days
    mock_db = MagicMock()
    mock_db.acquire.return_value.__aenter__.return_value = mock_conn

    # Purchase made 2 days ago
    two_days_ago = time.time() - (2 * 86400)
    mock_charge = {"amount": 5000, "created": two_days_ago}

    res = await validate_refund(
        customer_id="cust_1",
        charge_id="ch_1",
        amount_cents=2000,
        reason="CHANGED_MIND",  # valid reason, within 7 days, under limits
        db_pool=mock_db,
        stripe_charge_mock=mock_charge
    )
    
    assert res.approved is True
    assert "All checks passed" in res.reason
