import json
import uuid
from typing import Any, Dict, Optional
import stripe
import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from src.config import settings
from src.policy.audit_log import log_event

logger = structlog.get_logger()
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


async def process_stripe_webhook_event(event: Dict[str, Any], db_pool: Any, redis_client: Any) -> None:
    """Handles webhook logic asynchronously in the background to prevent blocking the response."""
    event_type = event.get("type")
    data = event.get("data", {})
    obj = data.get("object", {})

    logger.info("Processing Stripe webhook event in background", event_type=event_type)

    if event_type in ("charge.refunded", "charge.refund.updated"):
        charge_id = obj.get("id")
        amount_refunded = obj.get("amount_refunded", 0)
        
        if db_pool:
            async with db_pool.acquire() as conn:
                # Find matching order
                order = await conn.fetchrow(
                    "SELECT id, customer_id FROM orders WHERE stripe_charge_id = $1", 
                    charge_id
                )
                if order:
                    order_id = order["id"]
                    customer_id = order["customer_id"]

                    # 1. Update order status to refunded
                    await conn.execute("UPDATE orders SET status = 'refunded' WHERE id = $1", order_id)
                    logger.info("Updated order status to refunded", order_id=order_id)

                    # 2. Add to refunds table so it counts against rolling guardrail limits
                    refund_id = f"ref_{uuid.uuid4().hex[:8]}"
                    await conn.execute(
                        """
                        INSERT INTO refunds (id, customer_id, charge_id, amount_cents, reason)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        refund_id,
                        customer_id,
                        charge_id,
                        amount_refunded,
                        "Confirmed via Stripe Webhook"
                    )

                    # 3. Log event to audit logs
                    conversation_id = f"conv_webhook_{order_id}"
                    await log_event(
                        conversation_id=conversation_id,
                        event_type="REFUND_CONFIRMED",
                        payload={"charge_id": charge_id, "order_id": order_id, "amount": amount_refunded},
                        db_pool=db_pool,
                        actor="stripe_webhook"
                    )

                    # 4. Stream update to Redis stream "order_updates"
                    if redis_client:
                        try:
                            await redis_client.xadd(
                                "order_updates",
                                {"order_id": order_id, "status": "refunded"}
                            )
                            logger.info("Streamed order update to Redis stream", order_id=order_id)
                        except Exception as e:
                            logger.error("Failed to stream to Redis order_updates", error=str(e))

    elif event_type == "payment_intent.payment_failed":
        pi_id = obj.get("id")
        customer_id = obj.get("customer") or "unknown_customer"
        last_error = obj.get("last_payment_error") or {}
        error_message = last_error.get("message", "Unknown Stripe Error")

        # Log event to audit logs
        conversation_id = f"conv_webhook_fail_{pi_id[:8]}"
        if db_pool:
            await log_event(
                conversation_id=conversation_id,
                event_type="PAYMENT_FAILED",
                payload={"payment_intent_id": pi_id, "customer_id": customer_id, "error": error_message},
                db_pool=db_pool,
                actor="stripe_webhook"
            )

            # Flag customer for review
            if customer_id != "unknown_customer":
                try:
                    async with db_pool.acquire() as conn:
                        await conn.execute("UPDATE customers SET tier = 'review' WHERE id = $1", customer_id)
                        logger.warn("Customer flagged for review due to payment failure", customer_id=customer_id)
                except Exception as e:
                    logger.error("Failed to update customer tier to review", error=str(e))


@router.post("/stripe")
async def stripe_webhook(request: Request, background_tasks: BackgroundTasks) -> Dict[str, bool]:
    """Receives and verifies Stripe webhook events, returning 200 within 5 seconds."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    secret = settings.STRIPE_WEBHOOK_SECRET.get_secret_value()

    try:
        # Mock mode bypass if signature is not present and secret is default
        if secret == "whsec_mock" and not sig_header:
            event = stripe.Event.construct_from(json.loads(payload), key=settings.STRIPE_SECRET_KEY.get_secret_value())
        else:
            event = stripe.Webhook.construct_event(payload, sig_header, secret)
    except Exception as e:
        logger.warn("Stripe webhook verification failed", error=str(e))
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    db_pool = getattr(request.app.state, "db_pool", None)
    redis_client = getattr(request.app.state, "redis_client", None)

    # Offload work to BackgroundTasks
    background_tasks.add_task(
        process_stripe_webhook_event,
        event=event,
        db_pool=db_pool,
        redis_client=redis_client
    )

    return {"received": True}
