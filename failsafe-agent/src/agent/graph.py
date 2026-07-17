import contextvars
import json
import pickle
from typing import Any, Dict, Optional
import structlog
from langgraph.graph import StateGraph, END, START

from src.agent.state import AgentState, init_state
from src.agent.nodes.classifier import classify_intent
from src.agent.nodes.main_agent import run_agent as raw_run_agent
from src.agent.nodes.escalation_gate import should_escalate as raw_should_escalate
from src.observability.tracing import conversation_span, set_conversation_outcome
from src.policy.audit_log import (
    log_event,
    CONVERSATION_START,
    TOOL_CALLED,
    RESOLVED,
    ESCALATED,
)

logger = structlog.get_logger()

# ContextVars to manage non-serializable database and redis connections safely
db_pool_var = contextvars.ContextVar("db_pool", default=None)
redis_client_var = contextvars.ContextVar("redis_client", default=None)


# --- Define Node Wrappers to inject ContextVars ---

async def classifier_node(state: AgentState) -> AgentState:
    return await classify_intent(state)


async def agent_node(state: AgentState) -> AgentState:
    redis_client = redis_client_var.get(None)
    return await raw_run_agent(state, redis_client=redis_client)


def escalation_gate_node(state: AgentState) -> AgentState:
    # No-op node that serves as the routing anchor
    return state


async def escalate_node(state: AgentState) -> AgentState:
    db_pool = db_pool_var.get(None)
    redis_client = redis_client_var.get(None)
    await raw_should_escalate(state, db_pool=db_pool, redis_client=redis_client)
    return state


def end_node(state: AgentState) -> AgentState:
    state["resolved"] = True
    return state


async def should_escalate_edge(state: AgentState) -> str:
    db_pool = db_pool_var.get(None)
    redis_client = redis_client_var.get(None)
    return await raw_should_escalate(state, db_pool=db_pool, redis_client=redis_client)


# --- Build StateGraph ---

workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("classifier", classifier_node)
workflow.add_node("agent", agent_node)
workflow.add_node("escalation_gate", escalation_gate_node)
workflow.add_node("escalate", escalate_node)
workflow.add_node("end", end_node)

# Add edges
workflow.add_edge(START, "classifier")
workflow.add_edge("classifier", "agent")
workflow.add_edge("agent", "escalation_gate")

# Add conditional routing from gate
workflow.add_conditional_edges(
    "escalation_gate",
    should_escalate_edge,
    {
        "escalate": "escalate",
        "continue": "end"
    }
)

workflow.add_edge("escalate", END)
workflow.add_edge("end", END)

# Compile LangGraph application
app = workflow.compile()


# --- Execution Harness ---

async def run_conversation(
    customer_id: str,
    message: str,
    conversation_id: Optional[str] = None,
    db_pool: Optional[Any] = None,
    redis_client: Optional[Any] = None,
) -> AgentState:
    """
    Main invocation harness. Loads session state from Redis if exists,
    feeds the new user message, executes the LangGraph application,
    saves the final state to Redis, and returns it.
    """
    # 1. Set ContextVars for database and cache connections
    db_token = db_pool_var.set(db_pool)
    redis_token = redis_client_var.set(redis_client)

    state: AgentState
    redis_key = f"session:{conversation_id}" if conversation_id else None

    # 2. Retrieve or Initialize state
    if redis_client and redis_key:
        cached = await redis_client.get(redis_key)
        if cached:
            try:
                state = pickle.loads(cached)
                # Append new message to existing conversation history
                state["messages"].append({"role": "user", "content": message})
                logger.info("Resumed active conversation state from Redis", conversation_id=conversation_id)
            except Exception as e:
                logger.error("Failed to parse cached session state, initializing fresh state", error=str(e))
                state = init_state(customer_id, message)
        else:
            state = init_state(customer_id, message)
    else:
        state = init_state(customer_id, message)
        if conversation_id:
            state["conversation_id"] = conversation_id

    # 3. Log CONVERSATION_START audit event
    if db_pool:
        try:
            await log_event(
                conversation_id=state["conversation_id"],
                event_type=CONVERSATION_START,
                payload={"customer_id": customer_id, "message_preview": message[:50]},
                db_pool=db_pool,
            )
        except Exception as e:
            logger.warning("Failed to log CONVERSATION_START audit event", error=str(e))

    # 4. Invoke LangGraph application wrapped in a root OTel span
    try:
        async with conversation_span(
            conversation_id=state["conversation_id"],
            customer_id=customer_id,
        ) as conv_span:
            final_state = await app.ainvoke(state)
            set_conversation_outcome(
                span=conv_span,
                intent=final_state.get("intent"),
                resolved=final_state.get("resolved", False),
                escalated=final_state.get("escalated", False),
                total_tool_calls=len(final_state.get("tool_call_log", [])),
            )
    except Exception as e:
        logger.error("LangGraph execution encountered an error", error=str(e))
        raise e
    finally:
        # Reset ContextVars
        db_pool_var.reset(db_token)
        redis_client_var.reset(redis_token)

    # 5. Log outcome audit event (RESOLVED or ESCALATED)
    if db_pool:
        try:
            outcome_event = ESCALATED if final_state.get("escalated") else RESOLVED
            await log_event(
                conversation_id=final_state["conversation_id"],
                event_type=outcome_event,
                payload={
                    "resolved": final_state.get("resolved", False),
                    "escalated": final_state.get("escalated", False),
                    "tool_calls": len(final_state.get("tool_call_log", [])),
                },
                db_pool=db_pool,
            )
        except Exception as e:
            logger.warning("Failed to log outcome audit event", error=str(e))

    # 6. Save updated state back to Redis
    if redis_client:
        save_key = f"session:{final_state['conversation_id']}"
        try:
            # Cache state for 24 hours (86400 seconds)
            await redis_client.set(save_key, pickle.dumps(final_state), ex=86400)
            logger.info("Saved conversation state to Redis", conversation_id=final_state["conversation_id"])
        except Exception as e:
            logger.error("Failed to save state to Redis", error=str(e))

    return final_state
