import re
from typing import Any, AsyncGenerator, Dict, List, Optional
from contextlib import asynccontextmanager
import aiosqlite
import asyncpg
import structlog
from src.config import settings

logger = structlog.get_logger()

_pool = None


class SqliteConnWrapper:
    def __init__(self, conn: aiosqlite.Connection):
        self._conn = conn

    def _convert_query(self, query: str) -> str:
        return re.sub(r"\$\d+", "?", query)

    async def fetchrow(self, query: str, *args) -> Optional[Dict[str, Any]]:
        q = self._convert_query(query)
        self._conn.row_factory = aiosqlite.Row
        cleaned_args = [str(a) if hasattr(a, "hex") else a for a in args]
        async with self._conn.execute(q, cleaned_args) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def fetchval(self, query: str, *args) -> Any:
        q = self._convert_query(query)
        cleaned_args = [str(a) if hasattr(a, "hex") else a for a in args]
        async with self._conn.execute(q, cleaned_args) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

    async def fetch(self, query: str, *args) -> List[Dict[str, Any]]:
        q = self._convert_query(query)
        self._conn.row_factory = aiosqlite.Row
        cleaned_args = [str(a) if hasattr(a, "hex") else a for a in args]
        async with self._conn.execute(q, cleaned_args) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def execute(self, query: str, *args) -> None:
        q = self._convert_query(query)
        cleaned_args = [str(a) if hasattr(a, "hex") else a for a in args]
        await self._conn.execute(q, cleaned_args)
        await self._conn.commit()


class LocalSqlitePool:
    def __init__(self, db_path: str = "autoforge.db"):
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None

    async def init_db(self):
        self._conn = await aiosqlite.connect(self.db_path)
        await self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                issue_number INTEGER,
                repo_full_name TEXT,
                title TEXT,
                body TEXT,
                status TEXT,
                created_at TEXT,
                updated_at TEXT,
                base_commit_sha TEXT
            )
            """
        )
        await self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_runs (
                id TEXT PRIMARY KEY,
                task_id TEXT,
                iteration INTEGER,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                model TEXT,
                tool_calls TEXT,
                output_summary TEXT,
                started_at TEXT,
                finished_at TEXT
            )
            """
        )
        await self._conn.commit()
        try:
            await self._conn.execute("ALTER TABLE tasks ADD COLUMN patch_diff TEXT")
            await self._conn.commit()
        except Exception:
            pass
        try:
            await self._conn.execute("ALTER TABLE tasks ADD COLUMN summary TEXT")
            await self._conn.commit()
        except Exception:
            pass

    @asynccontextmanager
    async def acquire(self):
        if self._conn is None:
            await self.init_db()
        yield SqliteConnWrapper(self._conn)

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None


async def get_db_pool():
    global _pool
    if _pool is None:
        try:
            _pool = await asyncpg.create_pool(
                dsn=settings.database_url.get_secret_value(),
                min_size=1,
                max_size=10,
            )
        except Exception as e:
            logger.warn("Postgres unavailable, using local SQLite pool (autoforge.db)", error=str(e))
            local_pool = LocalSqlitePool()
            await local_pool.init_db()
            _pool = local_pool
    return _pool


async def close_db_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def get_db_conn():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        yield conn
