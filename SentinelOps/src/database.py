import re
import json
import hashlib
import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
import aiosqlite
import structlog
from src.config import settings

logger = structlog.get_logger()

_pool: Optional["LocalSqlitePool"] = None


class SqliteConnWrapper:
    def __init__(self, conn: aiosqlite.Connection):
        self._conn = conn

    def _convert_query(self, query: str) -> str:
        return re.sub(r"\$\d+", "?", query)

    async def fetchrow(self, query: str, *args: Any) -> Optional[Dict[str, Any]]:
        q = self._convert_query(query)
        self._conn.row_factory = aiosqlite.Row
        cleaned_args = [str(a) if hasattr(a, "hex") else a for a in args]
        async with self._conn.execute(q, cleaned_args) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def fetchval(self, query: str, *args: Any) -> Any:
        q = self._convert_query(query)
        cleaned_args = [str(a) if hasattr(a, "hex") else a for a in args]
        async with self._conn.execute(q, cleaned_args) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

    async def fetch(self, query: str, *args: Any) -> List[Dict[str, Any]]:
        q = self._convert_query(query)
        self._conn.row_factory = aiosqlite.Row
        cleaned_args = [str(a) if hasattr(a, "hex") else a for a in args]
        async with self._conn.execute(q, cleaned_args) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def execute(self, query: str, *args: Any) -> None:
        q = self._convert_query(query)
        cleaned_args = [str(a) if hasattr(a, "hex") else a for a in args]
        await self._conn.execute(q, cleaned_args)
        await self._conn.commit()


class LocalSqlitePool:
    def __init__(self, db_path: str = "sentinelops.db"):
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None

    async def init_db(self):
        self._conn = await aiosqlite.connect(self.db_path)
        await self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS incidents (
                id TEXT PRIMARY KEY,
                incident_number INTEGER,
                service TEXT,
                severity TEXT,
                title TEXT,
                description TEXT,
                status TEXT,
                root_cause TEXT,
                remediation_patch TEXT,
                confidence_score REAL,
                risk_level TEXT,
                eval_passed BOOLEAN,
                audit_hash TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        await self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_actions (
                id TEXT PRIMARY KEY,
                incident_id TEXT,
                agent_role TEXT,
                action_type TEXT,
                summary TEXT,
                payload TEXT,
                created_at TEXT
            )
            """
        )
        await self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_ledger (
                id TEXT PRIMARY KEY,
                incident_id TEXT,
                event_type TEXT,
                payload TEXT,
                previous_hash TEXT,
                hash TEXT,
                created_at TEXT
            )
            """
        )
        await self._conn.commit()

    @asynccontextmanager
    async def acquire(self):
        if self._conn is None:
            await self.init_db()
        yield SqliteConnWrapper(self._conn)

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None


async def get_db_pool() -> LocalSqlitePool:
    global _pool
    if _pool is None:
        _pool = LocalSqlitePool(settings.database_url)
        await _pool.init_db()
    return _pool


async def close_db_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def append_audit_entry(incident_id: str, event_type: str, payload: Dict[str, Any]) -> str:
    pool = await get_db_pool()
    entry_id = f"aud_{uuid.uuid4().hex[:8]}"
    now_str = datetime.now(timezone.utc).isoformat()

    prev_hash = "GENESIS_ROOT"
    async with pool.acquire() as conn:
        last_entry = await conn.fetchrow(
            "SELECT hash FROM audit_ledger WHERE incident_id = $1 ORDER BY created_at DESC LIMIT 1",
            incident_id,
        )
        if last_entry and last_entry.get("hash"):
            prev_hash = last_entry["hash"]

        payload_json = json.dumps(payload, sort_keys=True)
        raw_hash_data = f"{prev_hash}|{incident_id}|{event_type}|{payload_json}|{now_str}"
        entry_hash = hashlib.sha256(raw_hash_data.encode("utf-8")).hexdigest()

        await conn.execute(
            """
            INSERT INTO audit_ledger (id, incident_id, event_type, payload, previous_hash, hash, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            entry_id,
            incident_id,
            event_type,
            payload_json,
            prev_hash,
            entry_hash,
            now_str,
        )
    return entry_hash
