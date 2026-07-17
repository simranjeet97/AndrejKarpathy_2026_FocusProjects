import datetime
import hashlib
import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.policy.audit_log import log_event, verify_chain, CONVERSATION_START, RESOLVED


@pytest.mark.asyncio
async def test_log_event_first_and_second() -> None:
    # Mock DB Connection
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = None  # No previous hash, defaults to GENESIS
    mock_db = MagicMock()
    mock_db.acquire.return_value.__aenter__.return_value = mock_conn

    # 1. Log First Event
    evt1_id = await log_event(
        conversation_id="conv_abc",
        event_type=CONVERSATION_START,
        payload={"started": True},
        db_pool=mock_db,
    )
    
    assert evt1_id.startswith("evt_")
    assert mock_conn.execute.call_count == 1
    
    # Extract details of first write
    sql_args = mock_conn.execute.call_args[0]
    first_hash = sql_args[6]
    
    # 2. Log Second Event (now return first_hash as the previous hash)
    mock_conn.fetchrow.return_value = {"hash": first_hash}
    mock_conn.execute.reset_mock()
    
    evt2_id = await log_event(
        conversation_id="conv_abc",
        event_type=RESOLVED,
        payload={"resolved": True},
        db_pool=mock_db,
    )
    
    assert evt2_id.startswith("evt_")
    assert mock_conn.execute.call_count == 1
    
    second_sql_args = mock_conn.execute.call_args[0]
    # Check that it builds off of first_hash
    second_inserted_payload = second_sql_args[5]
    second_inserted_date = second_sql_args[7]
    
    # Manually compute expected hash
    expected_data = f"{first_hash}{json.dumps({'resolved': True}, sort_keys=True)}{second_inserted_date.isoformat()}"
    expected_hash = hashlib.sha256(expected_data.encode("utf-8")).hexdigest()
    
    assert second_sql_args[6] == expected_hash


@pytest.mark.asyncio
async def test_verify_chain_valid() -> None:
    # Pre-calculate a valid chain of two items
    dt1 = datetime.datetime.now(datetime.timezone.utc)
    p1 = {"a": 1}
    h1 = hashlib.sha256(f"GENESIS{json.dumps(p1, sort_keys=True)}{dt1.isoformat()}".encode("utf-8")).hexdigest()
    
    dt2 = datetime.datetime.now(datetime.timezone.utc)
    p2 = {"b": 2}
    h2 = hashlib.sha256(f"{h1}{json.dumps(p2, sort_keys=True)}{dt2.isoformat()}".encode("utf-8")).hexdigest()

    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = [
        {"id": "e1", "payload": p1, "hash": h1, "created_at": dt1},
        {"id": "e2", "payload": p2, "hash": h2, "created_at": dt2},
    ]
    mock_db = MagicMock()
    mock_db.acquire.return_value.__aenter__.return_value = mock_conn

    assert await verify_chain("conv_abc", mock_db) is True


@pytest.mark.asyncio
async def test_verify_chain_tampered() -> None:
    dt1 = datetime.datetime.now(datetime.timezone.utc)
    p1 = {"a": 1}
    h1 = hashlib.sha256(f"GENESIS{json.dumps(p1, sort_keys=True)}{dt1.isoformat()}".encode("utf-8")).hexdigest()

    mock_conn = AsyncMock()
    # Tamper: change payload value from 1 to 999 for first event
    mock_conn.fetch.return_value = [
        {"id": "e1", "payload": {"a": 999}, "hash": h1, "created_at": dt1},
    ]
    mock_db = MagicMock()
    mock_db.acquire.return_value.__aenter__.return_value = mock_conn

    assert await verify_chain("conv_abc", mock_db) is False
