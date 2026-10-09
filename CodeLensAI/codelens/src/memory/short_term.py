import logging
import time
from typing import Optional
import redis.asyncio as redis
from ..models import ContextPack, ReviewResponse

logger = logging.getLogger(__name__)


class InMemoryRedisClient:
    """Mock in-memory key-value client for environments without Redis / DragonflyDB."""

    def __init__(self):
        self._data: dict[str, str] = {}
        self._expiries: dict[str, float] = {}

    async def set(self, name: str, value: str, ex: Optional[int] = None) -> bool:
        self._data[name] = value
        if ex is not None:
            self._expiries[name] = time.time() + ex
        elif name in self._expiries:
            del self._expiries[name]
        return True

    async def get(self, name: str) -> Optional[str]:
        if name in self._data:
            expiry = self._expiries.get(name)
            if expiry is None or time.time() < expiry:
                return self._data[name]
            del self._data[name]
            if name in self._expiries:
                del self._expiries[name]
        return None

    async def delete(self, *names: str) -> int:
        count = 0
        for name in names:
            if name in self._data:
                del self._data[name]
                count += 1
            if name in self._expiries:
                del self._expiries[name]
        return count

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        self._data.clear()
        self._expiries.clear()


class ShortTermMemory:
    """DragonflyDB-compatible Redis short-term memory store with automatic in-memory fallback."""

    def __init__(self, url: str) -> None:
        """
        Initialize the ShortTermMemory connection.

        Args:
            url: Redis connection URL (e.g. redis://localhost:6379/0).
        """
        self.url = url
        self._fallback = InMemoryRedisClient()
        self._use_fallback = False
        try:
            self.redis = redis.from_url(url, decode_responses=True)
        except Exception:
            self.redis = None
            self._use_fallback = True

    async def _client(self):
        """Return the active Redis client or switch to in-memory fallback."""
        if self._use_fallback or self.redis is None:
            return self._fallback
        try:
            await self.redis.ping()
            return self.redis
        except Exception:
            self._use_fallback = True
            logger.info("Redis/DragonflyDB is not available. Using local in-memory store.")
            return self._fallback

    async def cache_context(self, pr_id: str, context_pack: ContextPack, ttl_seconds: int = 3600) -> None:
        """Cache a ContextPack object."""
        key = f"ctx:{pr_id}"
        try:
            client = await self._client()
            data_json = context_pack.model_dump_json()
            await client.set(key, data_json, ex=ttl_seconds)
            logger.info(f"Cached ContextPack for PR {pr_id} (TTL: {ttl_seconds}s)")
        except Exception as e:
            logger.error(f"Failed to cache ContextPack for PR {pr_id}: {e}", exc_info=True)

    async def get_context(self, pr_id: str) -> Optional[ContextPack]:
        """Retrieve a cached ContextPack object."""
        key = f"ctx:{pr_id}"
        try:
            client = await self._client()
            data_json = await client.get(key)
            if data_json:
                return ContextPack.model_validate_json(data_json)
        except Exception as e:
            logger.error(f"Failed to retrieve ContextPack for PR {pr_id}: {e}", exc_info=True)
        return None

    async def cache_review(self, pr_id: str, review: ReviewResponse, ttl_seconds: int = 86400) -> None:
        """Cache a ReviewResponse object."""
        key = f"rev:{pr_id}"
        try:
            client = await self._client()
            data_json = review.model_dump_json()
            await client.set(key, data_json, ex=ttl_seconds)
            logger.info(f"Cached ReviewResponse for PR {pr_id} (TTL: {ttl_seconds}s)")
        except Exception as e:
            logger.error(f"Failed to cache ReviewResponse for PR {pr_id}: {e}", exc_info=True)

    async def get_review(self, pr_id: str) -> Optional[ReviewResponse]:
        """Retrieve a cached ReviewResponse object."""
        key = f"rev:{pr_id}"
        try:
            client = await self._client()
            data_json = await client.get(key)
            if data_json:
                return ReviewResponse.model_validate_json(data_json)
        except Exception as e:
            logger.error(f"Failed to retrieve ReviewResponse for PR {pr_id}: {e}", exc_info=True)
        return None

    async def invalidate(self, pr_id: str) -> None:
        """Delete all cached keys associated with the PR ID."""
        keys = [f"ctx:{pr_id}", f"rev:{pr_id}"]
        try:
            client = await self._client()
            await client.delete(*keys)
            logger.info(f"Invalidated short term memory keys for PR {pr_id}")
        except Exception as e:
            logger.error(f"Failed to invalidate keys for PR {pr_id}: {e}", exc_info=True)

    async def health_check(self) -> bool:
        """Perform health check. Returns True if Redis is reachable or fallback is active."""
        if self._use_fallback:
            return True
        if self.redis is None:
            self._use_fallback = True
            return True
        try:
            await self.redis.ping()
            return True
        except Exception:
            self._use_fallback = True
            return True

    async def close(self) -> None:
        """Close connection resources."""
        if self.redis is not None and not self._use_fallback:
            try:
                await self.redis.close()
            except Exception:
                pass
        await self._fallback.close()
