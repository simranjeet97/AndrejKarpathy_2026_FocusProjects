import time
import structlog

from src.agent.state import AgentState, Intent
from src.config import settings
from src.resilience.fallback_llm import call_anthropic_api
from src.resilience.retry import with_retry
from src.resilience.timeout import with_timeout, TimeoutBudget

logger = structlog.get_logger()


async def classify_intent(state: AgentState) -> AgentState:
    """
    Classifies the user's intent from the latest message using the fast FALLBACK_MODEL.
    Uses TimeoutBudget to limit execution time and sets appropriate confidence scores.
    """
    start_time = time.time()
    
    # 1. Extract the latest user message content
    user_messages = [m for m in state["messages"] if m["role"] == "user"]
    if not user_messages:
        state["intent"] = Intent.UNCLEAR.value
        state["confidence_score"] = 0.3
        return state

    latest_content = user_messages[-1]["content"]

    # 2. Allocate a temporal budget for classification (25% of remaining budget, min 5.0s unless total remaining is smaller)
    budget = TimeoutBudget(total_seconds=state["timeout_budget_remaining"])
    sub_budget_seconds = max(5.0, min(budget.sub_budget(0.25).remaining(), budget.remaining()))

    system_prompt = (
        "Classify the customer message into exactly one intent. "
        "Reply with ONLY the intent name, nothing else. "
        "Valid intents: REFUND_REQUEST, POLICY_LOOKUP, ORDER_STATUS, COMPLAINT, GENERAL_INQUIRY, UNCLEAR."
    )

    api_messages = [{"role": "user", "content": latest_content}]

    try:
        # Define retryable API call
        @with_retry(max_attempts=settings.MAX_RETRIES)
        async def run_classification() -> dict:
            return await call_anthropic_api(
                model=settings.FALLBACK_MODEL,
                messages=api_messages,
                system_prompt=system_prompt,
            )

        # Run with timeout
        response = await with_timeout(
            run_classification(),
            timeout_seconds=sub_budget_seconds,
            operation_name="classify_intent",
        )

        # 3. Parse and clean raw response
        raw_text = response["content"][0]["text"].strip()
        cleaned_text = raw_text.replace('"', '').replace("'", "").upper()

        # Validate against Intent enum
        try:
            matched_intent = Intent(cleaned_text).value
        except ValueError:
            # Fallback pattern matching
            matched_intent = Intent.UNCLEAR.value
            for intent in Intent:
                if intent.value in cleaned_text:
                    matched_intent = intent.value
                    break

        state["intent"] = matched_intent
        
        # Adjust confidence if intent is UNCLEAR
        if matched_intent == Intent.UNCLEAR.value:
            state["confidence_score"] = 0.3
            
        logger.info("Classifier finished successfully", intent=matched_intent, confidence=state["confidence_score"])

    except Exception as e:
        logger.error("Classifier failed, defaulting to UNCLEAR", error=str(e))
        state["intent"] = Intent.UNCLEAR.value
        state["confidence_score"] = 0.3
        state["error_count"] += 1

    # 4. Deduct elapsed time from state timeout budget
    elapsed = time.time() - start_time
    state["timeout_budget_remaining"] = max(0.0, state["timeout_budget_remaining"] - elapsed)
    
    return state
