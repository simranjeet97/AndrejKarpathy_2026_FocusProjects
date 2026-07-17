import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import time

from src.tools.stripe_tools import check_refund_eligibility, issue_refund, lookup_charge


@pytest.mark.asyncio
@patch("stripe.Charge.retrieve")
async def test_check_refund_eligibility_eligible(mock_retrieve: MagicMock) -> None:
    # Under 30 days (e.g. 5 days ago)
    five_days_ago_timestamp = time.time() - (5 * 86400)
    mock_charge = {
        "id": "ch_123",
        "status": "succeeded",
        "created": five_days_ago_timestamp,
        "amount": 5000,
        "amount_refunded": 0,
    }
    mock_retrieve.return_value = mock_charge

    res = await check_refund_eligibility("ch_123")
    assert res["eligible"] is True
    assert res["amount_refundable"] == 5000
    assert res["days_since_purchase"] == 5
    mock_retrieve.assert_called_once_with("ch_123")


@pytest.mark.asyncio
@patch("stripe.Charge.retrieve")
async def test_check_refund_eligibility_ineligible_old(mock_retrieve: MagicMock) -> None:
    # Over 30 days (e.g. 40 days ago)
    forty_days_ago_timestamp = time.time() - (40 * 86400)
    mock_charge = {
        "id": "ch_123",
        "status": "succeeded",
        "created": forty_days_ago_timestamp,
        "amount": 5000,
        "amount_refunded": 0,
    }
    mock_retrieve.return_value = mock_charge

    res = await check_refund_eligibility("ch_123")
    assert res["eligible"] is False
    assert "exceeds 30-day limit" in res["reason"]


@pytest.mark.asyncio
@patch("stripe.Refund.create")
async def test_issue_refund(mock_refund_create: MagicMock) -> None:
    mock_refund_create.return_value = {
        "id": "re_123",
        "status": "succeeded",
        "amount": 3000,
    }

    # Mock Redis client for the idempotency decorator
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None

    res = await issue_refund(
        charge_id="ch_123",
        amount_cents=3000,
        reason="requested_by_customer",
        redis_client=mock_redis
    )

    assert res["id"] == "re_123"
    assert res["status"] == "succeeded"
    mock_refund_create.assert_called_once_with(
        charge="ch_123",
        amount=3000,
        reason="requested_by_customer"
    )


@pytest.mark.asyncio
@patch("stripe.Charge.retrieve")
async def test_lookup_charge(mock_retrieve: MagicMock) -> None:
    mock_retrieve.return_value = {"id": "ch_123", "status": "succeeded"}
    res = await lookup_charge("ch_123")
    assert res["id"] == "ch_123"
    assert res["status"] == "succeeded"
    mock_retrieve.assert_called_once_with("ch_123")
