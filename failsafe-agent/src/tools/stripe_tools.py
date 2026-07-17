import asyncio
import time
from typing import Any, Dict, Optional
import stripe
import structlog

from src.config import settings
from src.resilience.idempotency import idempotent
from src.resilience.retry import with_retry
from src.resilience.timeout import with_timeout

logger = structlog.get_logger()

# Set Stripe API Key from Configuration
stripe.api_key = settings.STRIPE_SECRET_KEY.get_secret_value()


async def check_refund_eligibility(charge_id: str) -> Dict[str, Any]:
    """
    Retrieves a Stripe charge and evaluates eligibility for a refund.
    Eligible only if charge status is 'succeeded' and purchased within 30 days.
    """
    async def _execute() -> Dict[str, Any]:
        charge = await asyncio.to_thread(stripe.Charge.retrieve, charge_id)
        
        created_time = charge.get("created", 0)
        status = charge.get("status", "")
        amount_refundable = charge.get("amount", 0) - charge.get("amount_refunded", 0)
        
        days_since_purchase = int((time.time() - created_time) / 86400)
        
        eligible = True
        reason = "Eligible"
        
        if status != "succeeded":
            eligible = False
            reason = f"Charge status is '{status}', not 'succeeded'"
        elif days_since_purchase > 30:
            eligible = False
            reason = f"Purchase made {days_since_purchase} days ago (exceeds 30-day limit)"
        elif amount_refundable <= 0:
            eligible = False
            reason = "No remaining refundable balance"
            
        logger.info(
            "Stripe check_refund_eligibility completed",
            tool="check_refund_eligibility",
            charge_id=charge_id,
            result_status=status,
            eligible=eligible,
        )
        
        return {
            "eligible": eligible,
            "reason": reason,
            "amount_refundable": amount_refundable,
            "days_since_purchase": days_since_purchase,
        }

    return await with_timeout(_execute(), 10.0, "check_refund_eligibility")


# Key function for the idempotent decorator
def refund_key_fn(charge_id: str, amount_cents: int, **kwargs: Any) -> str:
    return f"refund:{charge_id}:{amount_cents}"


@idempotent(key_fn=refund_key_fn)
@with_retry(max_attempts=3, retryable_exceptions=(stripe.error.APIError,))
async def issue_refund(
    charge_id: str,
    amount_cents: int,
    reason: str,
    redis_client: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Issues a refund via Stripe. Wrapped with retry, timeout, and idempotency logic.
    """
    async def _execute() -> Dict[str, Any]:
        refund = await asyncio.to_thread(
            stripe.Refund.create,
            charge=charge_id,
            amount=amount_cents,
            reason=reason,
        )
        
        logger.info(
            "Stripe issue_refund completed",
            tool="issue_refund",
            charge_id=charge_id,
            result_status=refund.get("status"),
        )
        return dict(refund)

    if redis_client:
        from src.resilience.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker(redis_client, "stripe_refund")
        return await cb.call(with_timeout(_execute(), 10.0, "issue_refund"))
    return await with_timeout(_execute(), 10.0, "issue_refund")


async def lookup_charge(charge_id: str) -> Dict[str, Any]:
    """
    Retrieves full details of a specific Stripe charge.
    """
    async def _execute() -> Dict[str, Any]:
        charge = await asyncio.to_thread(stripe.Charge.retrieve, charge_id)
        
        logger.info(
            "Stripe lookup_charge completed",
            tool="lookup_charge",
            charge_id=charge_id,
            result_status=charge.get("status"),
        )
        return dict(charge)

    return await with_timeout(_execute(), 10.0, "lookup_charge")
