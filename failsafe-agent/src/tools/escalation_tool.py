import json
import time
import uuid
from typing import Any, Dict, List, Optional
import structlog

from src.config import settings

logger = structlog.get_logger()


async def escalate_to_human(
    conversation_id: str,
    customer_id: str,
    reason: str,
    confidence_score: float,
    conversation_history: List[Dict[str, Any]],
    tool_call_log: List[Dict[str, Any]],
    db_pool: Any,
    redis_client: Any,
) -> Dict[str, Any]:
    """
    Escalates an unresolved conversation to a human support agent.
    Saves context and logs to Postgres, streams notifications to Redis, 
    and marks the conversation session as escalated.
    """
    # 1. Derive Priority and ETA from confidence score
    if confidence_score < 0.3:
        priority = "urgent"
        estimated_response_hours = 0.5
    elif confidence_score < 0.6:
        priority = "high"
        estimated_response_hours = 1.0
    else:
        priority = "normal"
        estimated_response_hours = 2.0

    # 2. Build detailed context packet
    context_packet = {
        "customer_id": customer_id,
        "reason": reason,
        "confidence_score": confidence_score,
        "conversation_history": conversation_history,
        "tool_call_log": tool_call_log,
        "timestamp": time.time(),
        "agent_model_used": settings.PRIMARY_MODEL,
    }

    ticket_id = f"tkt_{uuid.uuid4().hex[:8]}"

    # 3. Save ticket to Postgres
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO tickets (id, conversation_id, status, priority, context_json)
                VALUES ($1, $2, 'open', $3, $4)
                """,
                ticket_id,
                conversation_id,
                priority,
                json.dumps(context_packet),
            )
        logger.info("Saved ticket to database", ticket_id=ticket_id, priority=priority)
    except Exception as e:
        logger.error("Failed to write ticket to Postgres", error=str(e))
        raise e

    # 4. Publish message to Redis stream "escalations"
    try:
        await redis_client.xadd(
            "escalations",
            {"ticket_id": ticket_id, "priority": priority}
        )
        logger.info("Published escalation event to Redis stream", ticket_id=ticket_id, stream="escalations")
    except Exception as e:
        logger.error("Failed to publish escalation to Redis stream", error=str(e))
        raise e

    # 5. Mark the conversation as escalated in Redis
    try:
        await redis_client.set(f"escalated:{conversation_id}", "true")
        logger.info("Conversation marked as escalated in Redis", conversation_id=conversation_id)
    except Exception as e:
        logger.warn("Failed to set escalation flag in Redis", conversation_id=conversation_id, error=str(e))

    return {
        "ticket_id": ticket_id,
        "estimated_response_hours": estimated_response_hours,
    }
