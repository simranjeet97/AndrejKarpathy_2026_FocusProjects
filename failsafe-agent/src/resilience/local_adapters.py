"""Local in-memory and SQLite adapters for Failsafe Agent.
Provides seamless execution without external Redis or PostgreSQL services.
"""

import asyncio
import os
import re
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
import aiosqlite
import structlog

logger = structlog.get_logger()


class LocalRedisPipeline:
    def __init__(self, client: "InMemoryRedis"):
        self.client = client
        self.commands = []

    def zremrangebyscore(self, key: str, min_score: Any, max_score: Any):
        self.commands.append(("zremrangebyscore", (key, min_score, max_score)))
        return self

    def zadd(self, key: str, mapping: Dict[str, float]):
        self.commands.append(("zadd", (key, mapping)))
        return self

    def zcard(self, key: str):
        self.commands.append(("zcard", (key,)))
        return self

    def zrange(self, key: str, start: int, end: int, withscores: bool = False):
        self.commands.append(("zrange", (key, start, end, withscores)))
        return self

    def expire(self, key: str, seconds: int):
        self.commands.append(("expire", (key, seconds)))
        return self

    async def execute(self) -> List[Any]:
        results = []
        for cmd, args in self.commands:
            if cmd == "zremrangebyscore":
                results.append(self.client._zremrangebyscore(*args))
            elif cmd == "zadd":
                results.append(self.client._zadd(*args))
            elif cmd == "zcard":
                results.append(self.client._zcard(*args))
            elif cmd == "zrange":
                results.append(self.client._zrange(*args))
            elif cmd == "expire":
                results.append(True)
        return results


class InMemoryRedis:
    """Mock Redis client for local execution."""

    def __init__(self):
        self._store: Dict[str, str] = {}
        self._zsets: Dict[str, Dict[str, float]] = {}
        self._expiries: Dict[str, float] = {}

    async def ping(self) -> bool:
        return True

    async def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        self._store[key] = value
        if ex is not None:
            self._expiries[key] = time.time() + ex
        return True

    async def get(self, key: str) -> Optional[str]:
        if key in self._store:
            exp = self._expiries.get(key)
            if exp is None or time.time() < exp:
                return self._store[key]
            del self._store[key]
            if key in self._expiries:
                del self._expiries[key]
        return None

    async def delete(self, *keys: str) -> int:
        c = 0
        for k in keys:
            if k in self._store:
                del self._store[k]
                c += 1
            if k in self._zsets:
                del self._zsets[k]
                c += 1
            if k in self._expiries:
                del self._expiries[k]
        return c

    def pipeline(self) -> LocalRedisPipeline:
        return LocalRedisPipeline(self)

    async def keys(self, pattern: str = "*") -> List[str]:
        import fnmatch
        matched = [k for k in self._store.keys() if fnmatch.fnmatch(k, pattern)]
        for k in self._zsets.keys():
            if fnmatch.fnmatch(k, pattern) and k not in matched:
                matched.append(k)
        return matched

    def _zremrangebyscore(self, key: str, min_val: Any, max_val: Any) -> int:
        zset = self._zsets.setdefault(key, {})
        # Parse max cutoff if e.g. "(123.45"
        cutoff = float(max_val.lstrip("(")) if isinstance(max_val, str) else float(max_val)
        to_del = [m for m, score in zset.items() if score < cutoff]
        for m in to_del:
            del zset[m]
        return len(to_del)

    def _zadd(self, key: str, mapping: Dict[str, float]) -> int:
        zset = self._zsets.setdefault(key, {})
        for m, score in mapping.items():
            zset[m] = float(score)
        return len(mapping)

    def _zcard(self, key: str) -> int:
        return len(self._zsets.get(key, {}))

    def _zrange(self, key: str, start: int, end: int, withscores: bool = False) -> List[Any]:
        zset = self._zsets.get(key, {})
        sorted_items = sorted(zset.items(), key=lambda x: x[1])
        if end == -1:
            items = sorted_items[start:]
        else:
            items = sorted_items[start : end + 1]
        if withscores:
            return [(m, s) for m, s in items]
        return [m for m, s in items]

    async def close(self) -> None:
        self._store.clear()
        self._zsets.clear()


class SqliteConnWrapper:
    def __init__(self, conn: aiosqlite.Connection):
        self._conn = conn

    def _convert_query(self, query: str) -> str:
        # Replace $1, $2, ... with ?
        return re.sub(r"\$\d+", "?", query)

    async def fetchrow(self, query: str, *args) -> Optional[Dict[str, Any]]:
        q = self._convert_query(query)
        self._conn.row_factory = aiosqlite.Row
        async with self._conn.execute(q, args) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def fetchval(self, query: str, *args) -> Any:
        q = self._convert_query(query)
        async with self._conn.execute(q, args) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

    async def fetch(self, query: str, *args) -> List[Dict[str, Any]]:
        q = self._convert_query(query)
        self._conn.row_factory = aiosqlite.Row
        async with self._conn.execute(q, args) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def execute(self, query: str, *args) -> None:
        q = self._convert_query(query)
        await self._conn.execute(q, args)
        await self._conn.commit()


class LocalSqlitePool:
    """Mock asyncpg Pool backed by local SQLite for audit events."""

    def __init__(self, db_path: str = "failsafe_audit.db"):
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None

    async def init_db(self):
        self._conn = await aiosqlite.connect(self.db_path)
        await self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                id TEXT PRIMARY KEY,
                conversation_id TEXT,
                event_type TEXT,
                actor TEXT,
                payload TEXT,
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
