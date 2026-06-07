import re
import time
import stripe
from src.config.settings import get_settings

class ToolError(Exception):
    """Exception raised for errors during tool execution."""
    pass

# Helper to initialize Stripe API key dynamically
def _init_stripe_key():
    try:
        stripe.api_key = get_settings().STRIPE_API_KEY.get_secret_value()
    except Exception:
        pass

async def get_stripe_churn_events(days_back: int = 30) -> list[dict]:
    """Fetch recent subscription cancellation events from Stripe."""
    _init_stripe_key()
    if not stripe.api_key:
        raise ToolError("Stripe API key is not configured.")

    try:
        start_timestamp = int(time.time()) - (days_back * 86400)
        events = stripe.Event.list(
            type="customer.subscription.deleted",
            created={"gte": start_timestamp},
            limit=100
        )
        
        churn_events = []
        for event in events.auto_paging_iter():
            sub = event.data.object
            customer_id = sub.customer
            cancelled_at = sub.canceled_at or event.created

            # Extract amount
            amount = 0
            if hasattr(sub, "plan") and sub.plan:
                amount = sub.plan.amount
            elif hasattr(sub, "items") and sub.items.data:
                amount = sub.items.data[0].plan.amount

            # Extract cancellation reason
            reason = "unspecified"
            if hasattr(sub, "cancellation_details") and sub.cancellation_details:
                reason = sub.cancellation_details.get("reason") or "unspecified"

            churn_events.append({
                "customer_id": customer_id,
                "cancelled_at": cancelled_at,
                "amount": amount,
                "reason": reason
            })
            
        return churn_events
    except stripe.error.StripeError as e:
        raise ToolError(f"Stripe API call failed: {e}") from e

async def get_stripe_mrr() -> dict:
    """Get current MRR from active Stripe subscriptions."""
    _init_stripe_key()
    if not stripe.api_key:
        raise ToolError("Stripe API key is not configured.")

    try:
        mrr_cents = 0
        customer_ids = set()
        subs = stripe.Subscription.list(status="active", limit=100)
        
        for sub in subs.auto_paging_iter():
            customer_ids.add(sub.customer)
            amount = 0
            if hasattr(sub, "plan") and sub.plan:
                amount = sub.plan.amount
            elif hasattr(sub, "items") and sub.items.data:
                amount = sub.items.data[0].plan.amount
            
            quantity = getattr(sub, "quantity", 1) or 1
            mrr_cents += amount * quantity
            
        return {
            "mrr_cents": mrr_cents,
            "customer_count": len(customer_ids)
        }
    except stripe.error.StripeError as e:
        raise ToolError(f"Stripe API call failed: {e}") from e

async def get_stripe_customer_segment(customer_id: str) -> dict:
    """Get segment/plan info for a specific Stripe customer."""
    # Regex validation on customer_id
    if not re.match(r"^cus_[a-zA-Z0-9]+$", customer_id):
        raise ValueError("Invalid customer_id format. Must match r'^cus_[a-zA-Z0-9]+$'")

    _init_stripe_key()
    if not stripe.api_key:
        raise ToolError("Stripe API key is not configured.")

    try:
        customer = stripe.Customer.retrieve(customer_id, expand=["subscriptions"])
        subs = customer.get("subscriptions", {}).get("data", [])
        
        plan_name = "None"
        mrr_cents = 0
        status = "inactive"
        created_at = customer.created

        if subs:
            active_sub = subs[0]
            status = active_sub.status
            if hasattr(active_sub, "plan") and active_sub.plan:
                plan_name = active_sub.plan.nickname or active_sub.plan.id
                mrr_cents = active_sub.plan.amount * getattr(active_sub, "quantity", 1)
            elif hasattr(active_sub, "items") and active_sub.items.data:
                plan_name = active_sub.items.data[0].plan.nickname or active_sub.items.data[0].plan.id
                mrr_cents = active_sub.items.data[0].plan.amount * getattr(active_sub, "quantity", 1)

        return {
            "customer_id": customer_id,
            "plan": plan_name,
            "mrr_cents": mrr_cents,
            "created_at": created_at,
            "status": status
        }
    except stripe.error.StripeError as e:
        raise ToolError(f"Stripe API call failed: {e}") from e
