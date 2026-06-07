import hashlib
import json
import logging
import time
from datetime import date, timedelta
from typing import Optional
from src.models import AgentResponse, ToolCall, QueryResult

logger = logging.getLogger(__name__)

class InMemoryRedisClient:
    """Mock interface mimicking redis.asyncio client methods for purely in-memory operations."""

    def __init__(self):
        self._data = {}  # key -> value
        self._expiries = {}  # key -> timestamp

    async def setex(self, key: str, ttl: int, value: str) -> bool:
        self._data[key] = value
        self._expiries[key] = time.time() + ttl
        return True

    async def get(self, key: str) -> Optional[str]:
        if key in self._data:
            expiry = self._expiries.get(key)
            if expiry is None or time.time() < expiry:
                return self._data[key]
            else:
                del self._data[key]
                if key in self._expiries:
                    del self._expiries[key]
        return None

    async def lpush(self, key: str, *values: str) -> int:
        if key not in self._data:
            self._data[key] = []
        for val in reversed(values):
            self._data[key].insert(0, val)
        return len(self._data[key])

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        lst = self._data.get(key, [])
        if not isinstance(lst, list):
            return []
        if end == -1:
            return lst[start:]
        return lst[start:end+1]

    async def ltrim(self, key: str, start: int, end: int) -> bool:
        lst = self._data.get(key, [])
        if not isinstance(lst, list):
            return False
        if end == -1:
            self._data[key] = lst[start:]
        else:
            self._data[key] = lst[start:end+1]
        return True

    async def expire(self, key: str, ttl: int) -> bool:
        self._expiries[key] = time.time() + ttl
        return True

    async def keys(self, pattern: str) -> list[str]:
        import fnmatch
        return [k for k in self._data.keys() if fnmatch.fnmatch(k, pattern)]

    async def delete(self, *keys: str) -> int:
        count = 0
        for k in keys:
            if k in self._data:
                del self._data[k]
                count += 1
            if k in self._expiries:
                del self._expiries[k]
        return count

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        pass
        
    def pipeline(self, transaction=True):
        class MockPipeline:
            def __init__(self, client):
                self.client = client
                self.commands = []

            def lpush(self, key, data):
                self.commands.append(lambda: self.client.lpush(key, data))
                return self

            def ltrim(self, key, start, end):
                self.commands.append(lambda: self.client.ltrim(key, start, end))
                return self

            def expire(self, key, ttl):
                self.commands.append(lambda: self.client.expire(key, ttl))
                return self

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

            async def execute(self):
                for cmd in self.commands:
                    await cmd()
                return []
                
        return MockPipeline(self)


class AgentMemory:
    """Memory layer storing data purely in-memory (local DB only, no Redis, no Dragonfly)."""

    def __init__(self, url: Optional[str] = None):
        self.url = url
        self.client = InMemoryRedisClient()
        logger.info("Initializing Memory Layer: Pure local in-memory caching and logging mode.")

    def _hash_query(self, query: str) -> str:
        """Hash a query string using MD5."""
        return hashlib.md5(query.encode("utf-8")).hexdigest()

    async def cache_response(self, query: str, response: AgentResponse, ttl: int = 3600) -> None:
        """Cache an AgentResponse keyed by the query hash."""
        key = f"response:{self._hash_query(query)}"
        await self.client.setex(key, ttl, response.model_dump_json())

    async def get_cached_response(self, query: str) -> Optional[AgentResponse]:
        """Retrieve a cached AgentResponse by query."""
        key = f"response:{self._hash_query(query)}"
        data = await self.client.get(key)
        if data:
            try:
                return AgentResponse.model_validate_json(data)
            except Exception:
                pass
        return None

    async def log_tool_call(self, tool_call: ToolCall) -> None:
        """Log a tool call by appending it to a date-partitioned list."""
        today_str = date.today().isoformat()
        key = f"tool_log:{today_str}"
        data = tool_call.model_dump_json()
        async with self.client.pipeline(transaction=True) as pipe:
            pipe.lpush(key, data)
            pipe.ltrim(key, 0, 999)
            pipe.expire(key, 14 * 86400)
            await pipe.execute()

    async def get_tool_usage_stats(self, days: int = 7) -> dict[str, int]:
        """Count calls per tool_name across logs from recent days."""
        stats = {}
        today = date.today()
        for i in range(days):
            day_str = (today - timedelta(days=i)).isoformat()
            key = f"tool_log:{day_str}"
            logs = await self.client.lrange(key, 0, -1)
            for log in logs:
                try:
                    data = json.loads(log)
                    tool_name = data.get("input", {}).get("tool_name")
                    if tool_name:
                        stats[tool_name] = stats.get(tool_name, 0) + 1
                except Exception:
                    continue
        return stats

    async def cache_query_result(self, query_name: str, result: QueryResult, ttl: int = 300) -> None:
        """Cache expensive DB query results for 5 minutes."""
        key = f"query:{self._hash_query(query_name)}"
        await self.client.setex(key, ttl, result.model_dump_json())

    async def get_cached_query(self, query_name: str) -> Optional[QueryResult]:
        """Retrieve cached QueryResult by query name."""
        key = f"query:{self._hash_query(query_name)}"
        data = await self.client.get(key)
        if data:
            try:
                return QueryResult.model_validate_json(data)
            except Exception:
                pass
        return None

    async def health_check(self) -> bool:
        """Verify connection to Memory layer (always True for local fallback)."""
        return True

    async def close(self) -> None:
        """Close connection client (noop)."""
        pass
