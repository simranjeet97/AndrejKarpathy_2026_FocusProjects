import time
from typing import Any, NamedTuple, Optional
import stripe
import structlog

from src.config import settings

logger = structlog.get_logger()


class GuardrailViolationError(ValueError):
    """Exception raised when a refund violates system policy guardrails."""
    pass


class GuardrailResult(NamedTuple):
    approved: bool
    reason: str


async def validate_refund(
    customer_id: str,
    charge_id: str,
    amount_cents: int,
    reason: str,
    db_pool: Any,
    stripe_charge_mock: Optional[dict] = None,
) -> GuardrailResult:
    """
    Evaluates refund arguments against policy rules:
    1. Positive amount and <= original charge amount.
    2. Under rolling 3-refund maximum in 30 days.
    3. Reason matches policy list.
    4. CHANGED_MIND claims raised <= 7 days since purchase.
    """
    # Rule 3: Valid refund reason checking
    allowed_reasons = {"DEFECTIVE", "NOT_RECEIVED", "DUPLICATE_CHARGE", "CHANGED_MIND", "UNAUTHORIZED"}
    if reason not in allowed_reasons:
        msg = f"Invalid refund reason '{reason}'. Allowed values: {', '.join(allowed_reasons)}"
        logger.warn("Guardrail decision", rule="Reason Validation", outcome="fail", reason=msg)
        raise GuardrailViolationError(msg)
    logger.info("Guardrail decision", rule="Reason Validation", outcome="pass")

    # Resolve Stripe Charge info
    if stripe_charge_mock:
        charge = stripe_charge_mock
    else:
        import asyncio
        stripe.api_key = settings.STRIPE_SECRET_KEY.get_secret_value()
        try:
            charge = await asyncio.to_thread(stripe.Charge.retrieve, charge_id)
        except Exception as e:
            msg = f"Failed to retrieve Stripe charge details: {str(e)}"
            logger.error("Guardrail decision", rule="Retrieve Charge", outcome="fail", reason=msg)
            raise GuardrailViolationError(msg)

    original_amount = charge.get("amount", 0)
    created_time = charge.get("created", 0)

    # Rule 1: Positive and within original amount boundary
    if amount_cents <= 0 or amount_cents > original_amount:
        msg = f"Refund amount ({amount_cents} cents) must be positive and <= original charge ({original_amount} cents)."
        logger.warn("Guardrail decision", rule="Amount Validation", outcome="fail", reason=msg)
        raise GuardrailViolationError(msg)
    logger.info("Guardrail decision", rule="Amount Validation", outcome="pass")

    # Rule 4: CHANGED_MIND within 7 days constraint
    if reason == "CHANGED_MIND":
        days_since_purchase = (time.time() - created_time) / 86400.0
        if days_since_purchase > 7.0:
            msg = f"CHANGED_MIND refunds are only allowed within 7 days of purchase. Current elapsed: {days_since_purchase:.1f} days."
            logger.warn("Guardrail decision", rule="Timeline Validation", outcome="fail", reason=msg)
            raise GuardrailViolationError(msg)
    logger.info("Guardrail decision", rule="Timeline Validation", outcome="pass")

    # Rule 2: Max 3 refunds per customer per 30 days
    try:
        async with db_pool.acquire() as conn:
            refund_count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM refunds 
                WHERE customer_id = $1 AND created_at >= NOW() - INTERVAL '30 days'
                """,
                customer_id,
            )
            if refund_count >= 3:
                msg = f"Customer has already received {refund_count} refunds in past 30 days (limit is 3)."
                logger.warn("Guardrail decision", rule="Rolling Window Count", outcome="fail", reason=msg)
                raise GuardrailViolationError(msg)
    except GuardrailViolationError:
        raise
    except Exception as e:
        logger.error("Database query failed during refund window check", error=str(e))
        raise GuardrailViolationError(f"Database validation failure: {str(e)}")
        
    logger.info("Guardrail decision", rule="Rolling Window Count", outcome="pass")

    logger.info("Guardrail check passed successfully", customer_id=customer_id, charge_id=charge_id)
    return GuardrailResult(approved=True, reason="All checks passed successfully.")
