from typing import Any, Dict, List, Optional
import time
from fastapi import APIRouter, Request, HTTPException, status
from pydantic import BaseModel, Field
import structlog

from src.agent.graph import run_conversation
from src.agent.state import init_state
from src.policy.pii_scrubber import scrub
from src.policy.audit_log import verify_chain

logger = structlog.get_logger()
router = APIRouter(prefix="/conversations", tags=["Conversations"])


# --- Pydantic Schemas with OpenAPI Examples ---

class CreateConversationRequest(BaseModel):
    customer_id: str = Field(..., description="The unique ID of the customer")
    message: str = Field(..., description="The opening message from the customer")

    model_config = {
        "json_schema_extra": {
            "example": {
                "customer_id": "cust_01",
                "message": "I would like a refund for order ord_101 because the item was defective."
            }
        }
    }


class AppendMessageRequest(BaseModel):
    message: str = Field(..., description="The follow-up message from the customer")

    model_config = {
        "json_schema_extra": {
            "example": {
                "message": "Yes, I purchased it 5 days ago. Can you check my eligibility?"
            }
        }
    }


class ConversationResponse(BaseModel):
    conversation_id: str
    response: str
    resolved: bool
    escalated: bool
    ticket_id: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "conversation_id": "conv_a1b2c3d4",
                "response": "I have verified your eligibility and processed the refund for you.",
                "resolved": True,
                "escalated": False,
                "ticket_id": None
            }
        }
    }


class ConversationDetailResponse(BaseModel):
    conversation_id: str
    status: str
    messages: List[Dict[str, Any]]
    tool_call_count: int
    created_at: float

    model_config = {
        "json_schema_extra": {
            "example": {
                "conversation_id": "conv_a1b2c3d4",
                "status": "resolved",
                "messages": [
                    {"role": "user", "content": "I want a refund"},
                    {"role": "assistant", "content": "I have processed your refund"}
                ],
                "tool_call_count": 2,
                "created_at": 1783459820.0
            }
        }
    }


# --- API Endpoints ---

@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(request: Request, body: CreateConversationRequest) -> Dict[str, Any]:
    """Starts a new conversation, applies PII scrubbing, and executes the LangGraph agent."""
    db_pool = getattr(request.app.state, "db_pool", None)
    redis_client = getattr(request.app.state, "redis_client", None)

    # Apply PII Scrubber to incoming query
    scrubbed_msg = scrub(body.message).scrubbed_text

    # Run conversation through LangGraph
    final_state = await run_conversation(
        customer_id=body.customer_id,
        message=scrubbed_msg,
        db_pool=db_pool,
        redis_client=redis_client
    )

    # Get the last assistant message
    assistant_responses = [
        m["content"] for m in final_state["messages"] 
        if m["role"] == "assistant"
    ]
    
    # Handle content blocks formatting
    last_response = ""
    if assistant_responses:
        last_block = assistant_responses[-1]
        if isinstance(last_block, str):
            last_response = last_block
        elif isinstance(last_block, list):
            text_blocks = [b["text"] for b in last_block if b.get("type") == "text"]
            last_response = "\n".join(text_blocks)

    ticket_id = None
    if final_state["escalated"] and final_state["tool_call_log"]:
        # Find if a ticket ID was returned from escalate_to_human tool
        for log in final_state["tool_call_log"]:
            if log["tool"] == "escalate_to_human" and log["status"] == "success":
                ticket_id = log["output"].get("ticket_id")

    return {
        "conversation_id": final_state["conversation_id"],
        "response": last_response,
        "resolved": final_state["resolved"],
        "escalated": final_state["escalated"],
        "ticket_id": ticket_id
    }


@router.post("/{id}/messages", response_model=ConversationResponse)
async def append_message(id: str, request: Request, body: AppendMessageRequest) -> Dict[str, Any]:
    """Appends a user message to an existing conversation and re-runs the LangGraph agent."""
    db_pool = getattr(request.app.state, "db_pool", None)
    redis_client = getattr(request.app.state, "redis_client", None)

    if not redis_client:
        raise HTTPException(status_code=500, detail="Redis client is not available")

    # Verify session exists
    session_key = f"session:{id}"
    cached = await redis_client.get(session_key)
    if not cached:
        raise HTTPException(status_code=404, detail="Conversation session not found")

    scrubbed_msg = scrub(body.message).scrubbed_text

    # Re-run conversation (run_conversation will automatically load and update state)
    final_state = await run_conversation(
        customer_id="",  # Loaded from session state
        message=scrubbed_msg,
        conversation_id=id,
        db_pool=db_pool,
        redis_client=redis_client
    )

    assistant_responses = [
        m["content"] for m in final_state["messages"] 
        if m["role"] == "assistant"
    ]
    
    last_response = ""
    if assistant_responses:
        last_block = assistant_responses[-1]
        if isinstance(last_block, str):
            last_response = last_block
        elif isinstance(last_block, list):
            text_blocks = [b["text"] for b in last_block if b.get("type") == "text"]
            last_response = "\n".join(text_blocks)

    ticket_id = None
    if final_state["escalated"] and final_state["tool_call_log"]:
        for log in final_state["tool_call_log"]:
            if log["tool"] == "escalate_to_human" and log["status"] == "success":
                ticket_id = log["output"].get("ticket_id")

    return {
        "conversation_id": final_state["conversation_id"],
        "response": last_response,
        "resolved": final_state["resolved"],
        "escalated": final_state["escalated"],
        "ticket_id": ticket_id
    }


@router.get("/{id}", response_model=ConversationDetailResponse)
async def get_conversation(id: str, request: Request) -> Dict[str, Any]:
    """Retrieves full conversation details from Redis cache."""
    redis_client = getattr(request.app.state, "redis_client", None)
    if not redis_client:
        raise HTTPException(status_code=500, detail="Redis client is not available")

    import pickle
    session_key = f"session:{id}"
    cached = await redis_client.get(session_key)
    if not cached:
        raise HTTPException(status_code=404, detail="Conversation session not found")

    try:
        state = pickle.loads(cached)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to decode session state: {str(e)}")

    # Derive status
    status_str = "active"
    if state.get("resolved"):
        status_str = "resolved"
    elif state.get("escalated"):
        status_str = "escalated"

    return {
        "conversation_id": state["conversation_id"],
        "status": status_str,
        "messages": state["messages"],
        "tool_call_count": len(state["tool_call_log"]),
        "created_at": state.get("tool_call_log", [{}])[0].get("timestamp", time.time()) if state.get("tool_call_log") else time.time()
    }


@router.get("/{id}/audit")
async def get_conversation_audit(id: str, request: Request) -> Dict[str, Any]:
    """Retrieves full audit logs for a given conversation and verifies chain integrity."""
    db_pool = getattr(request.app.state, "db_pool", None)
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database pool not available")

    # Verify integrity of the chain
    chain_valid = await verify_chain(id, db_pool)

    # Fetch rows
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, event_type, actor, payload, hash, created_at
            FROM audit_events
            WHERE conversation_id = $1
            ORDER BY created_at ASC, id ASC
            """,
            id
        )

    import json
    parsed_events = []
    for r in rows:
        payload_data = r["payload"]
        if isinstance(payload_data, str):
            payload_dict = json.loads(payload_data)
        else:
            payload_dict = payload_data

        parsed_events.append({
            "event_id": r["id"],
            "event_type": r["event_type"],
            "actor": r["actor"],
            "payload": payload_dict,
            "hash": r["hash"],
            "created_at": r["created_at"].isoformat()
        })

    return {
        "conversation_id": id,
        "chain_integrity_valid": chain_valid,
        "events": parsed_events
    }
