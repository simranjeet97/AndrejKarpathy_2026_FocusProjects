from enum import Enum
import uuid
from typing import Any, Dict, List, Optional, TypedDict


class Intent(str, Enum):
    REFUND_REQUEST = "REFUND_REQUEST"
    POLICY_LOOKUP = "POLICY_LOOKUP"
    ORDER_STATUS = "ORDER_STATUS"
    COMPLAINT = "COMPLAINT"
    GENERAL_INQUIRY = "GENERAL_INQUIRY"
    UNCLEAR = "UNCLEAR"


class AgentState(TypedDict):
    conversation_id: str
    customer_id: str
    messages: List[Dict[str, Any]]
    tool_call_log: List[Dict[str, Any]]
    confidence_score: float
    intent: Optional[str]
    escalated: bool
    resolved: bool
    error_count: int
    active_policies: List[str]
    refund_data: Optional[Dict[str, Any]]
    timeout_budget_remaining: float


def init_state(
    customer_id: str,
    first_message: str,
    timeout_budget: float = 28.0,
) -> AgentState:
    """
    Initializes a new AgentState for a conversation session.
    Generates a unique conversation ID and sets defaults for execution monitoring.
    """
    conversation_id = f"conv_{uuid.uuid4().hex[:8]}"
    return {
        "conversation_id": conversation_id,
        "customer_id": customer_id,
        "messages": [{"role": "user", "content": first_message}],
        "tool_call_log": [],
        "confidence_score": 1.0,
        "intent": None,
        "escalated": False,
        "resolved": False,
        "error_count": 0,
        "active_policies": [],
        "refund_data": None,
        "timeout_budget_remaining": timeout_budget,
    }
