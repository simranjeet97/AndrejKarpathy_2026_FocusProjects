import datetime
import hashlib
import json
import uuid
from typing import Any, Dict, List
import structlog

logger = structlog.get_logger()

# Supported Event Types
CONVERSATION_START = "CONVERSATION_START"
TOOL_CALLED = "TOOL_CALLED"
REFUND_ISSUED = "REFUND_ISSUED"
ESCALATED = "ESCALATED"
RESOLVED = "RESOLVED"
POLICY_CHECKED = "POLICY_CHECKED"
GUARDRAIL_VIOLATED = "GUARDRAIL_VIOLATED"


async def log_event(
    conversation_id: str,
    event_type: str,
    payload: Dict[str, Any],
    db_pool: Any,
    actor: str = "agent",
) -> str:
    """
    Appends an event to the tamper-evident audit log table.
    Hashes the payload cryptographically chained with the previous event's hash.
    """
    # 1. Fetch previous event hash for this conversation to build the chain link
    previous_hash = "GENESIS"
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT hash FROM audit_events 
                WHERE conversation_id = $1 
                ORDER BY created_at DESC, id DESC 
                LIMIT 1
                """,
                conversation_id,
            )
            if row:
                previous_hash = row["hash"]
    except Exception as e:
        logger.error("Failed to query previous audit hash", error=str(e))

    # 2. Formulate event properties
    event_id = f"evt_{uuid.uuid4().hex[:8]}"
    created_at = datetime.datetime.now(datetime.timezone.utc)
    
    # Sort keys for canonical representation
    canonical_payload = json.dumps(payload, sort_keys=True)

    # 3. Compute SHA-256 hash chaining previous_hash + payload + created_at
    data_to_hash = f"{previous_hash}{canonical_payload}{created_at.isoformat()}"
    event_hash = hashlib.sha256(data_to_hash.encode("utf-8")).hexdigest()

    # 4. Insert audit record
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO audit_events (id, conversation_id, event_type, actor, payload, hash, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                event_id,
                conversation_id,
                event_type,
                actor,
                canonical_payload,
                event_hash,
                created_at,
            )
        logger.info("Logged audit event", event_type=event_type, event_id=event_id)
    except Exception as e:
        logger.error("Failed to write audit event to Postgres", error=str(e))
        raise e

    return event_id


async def verify_chain(conversation_id: str, db_pool: Any) -> bool:
    """
    Retrieves the entire hash chain for a conversation and verifies its cryptographic integrity.
    Returns True if valid, False if tampering is detected.
    """
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, payload, hash, created_at FROM audit_events 
                WHERE conversation_id = $1 
                ORDER BY created_at ASC, id ASC
                """,
                conversation_id,
            )
    except Exception as e:
        logger.error("Failed to fetch audit chain for verification", error=str(e))
        return False

    if not rows:
        logger.warn("No audit records found for verification", conversation_id=conversation_id)
        return True

    previous_hash = "GENESIS"
    
    for row in rows:
        # Load and sort keys of the payload dict to match original encoding
        payload_data = row["payload"]
        if isinstance(payload_data, str):
            payload_dict = json.loads(payload_data)
        else:
            payload_dict = payload_data
            
        canonical_payload = json.dumps(payload_dict, sort_keys=True)
        created_at: datetime.datetime = row["created_at"]
        
        # Recalculate hash
        data_to_hash = f"{previous_hash}{canonical_payload}{created_at.isoformat()}"
        computed_hash = hashlib.sha256(data_to_hash.encode("utf-8")).hexdigest()
        
        if computed_hash != row["hash"]:
            logger.error(
                "Audit chain verification failed: TAMPERING DETECTED",
                event_id=row["id"],
                stored_hash=row["hash"],
                expected_hash=computed_hash,
            )
            return False
            
        previous_hash = row["hash"]

    logger.info("Audit chain verified successfully", conversation_id=conversation_id, chain_length=len(rows))
    return True
