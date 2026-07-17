from typing import Any, Optional
import structlog

from src.agent.state import AgentState
from src.tools.escalation_tool import escalate_to_human

logger = structlog.get_logger()


async def should_escalate(
    state: AgentState,
    db_pool: Optional[Any] = None,
    redis_client: Optional[Any] = None,
) -> str:
    """
    Conditional router node checking escalation triggers.
    If triggered, issues an escalation ticket and updates the conversation history.
    """
    confidence_low = state["confidence_score"] < 0.4
    error_threshold_reached = state["error_count"] >= 2
    escalation_requested = state["escalated"] is True
    timeout_exhausted = state["timeout_budget_remaining"] < 2.0

    trigger_escalation = (
        confidence_low 
        or error_threshold_reached 
        or escalation_requested 
        or timeout_exhausted
    )

    if trigger_escalation:
        logger.info(
            "Escalation gate triggered",
            conversation_id=state["conversation_id"],
            confidence_low=confidence_low,
            error_threshold_reached=error_threshold_reached,
            escalation_requested=escalation_requested,
            timeout_exhausted=timeout_exhausted,
        )

        # Determine escalation reason
        reason = "System Escalation Triggered"
        if confidence_low:
            reason = f"Low confidence score ({state['confidence_score']:.2f} < 0.4)"
        elif error_threshold_reached:
            reason = f"Error threshold exceeded (error count: {state['error_count']} >= 2)"
        elif timeout_exhausted:
            reason = f"Time budget exhausted ({state['timeout_budget_remaining']:.1f}s < 2.0s)"
        elif escalation_requested:
            reason = "Direct escalation requested by the agent/customer"

        # If not already marked as escalated, perform human escalation
        if not state["escalated"]:
            try:
                # Use default pools/clients if they exist, or rely on passed references
                if db_pool and redis_client:
                    ticket_res = await escalate_to_human(
                        conversation_id=state["conversation_id"],
                        customer_id=state["customer_id"],
                        reason=reason,
                        confidence_score=state["confidence_score"],
                        conversation_history=state["messages"],
                        tool_call_log=state["tool_call_log"],
                        db_pool=db_pool,
                        redis_client=redis_client,
                    )
                    import time
                    state["tool_call_log"].append({
                        "tool": "escalate_to_human",
                        "input": {
                            "conversation_id": state["conversation_id"],
                            "customer_id": state["customer_id"],
                            "reason": reason,
                        },
                        "output": ticket_res,
                        "status": "success",
                        "timestamp": time.time(),
                    })
                    eta = ticket_res.get("estimated_response_hours", 2.0)
                    msg = f"I am transferring your conversation to a human support agent. A ticket has been created, and we will follow up with you within {eta} hours."
                else:
                    msg = "I am transferring you to a human agent. They will follow up shortly."
                
                # Append human notification message
                state["messages"].append({
                    "role": "assistant",
                    "content": msg
                })
            except Exception as e:
                logger.error("Failed during human escalation call in gate", error=str(e))
                state["messages"].append({
                    "role": "assistant",
                    "content": "I am having trouble processing this right now. Rest assured, I have marked this for human support follow-up."
                })

            state["escalated"] = True
            state["resolved"] = False

        return "escalate"

    return "continue"
