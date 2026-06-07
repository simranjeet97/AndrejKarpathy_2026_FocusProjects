import logging
import redis.asyncio as redis
from typing import Optional
from ..models import ContextPack, ReviewResponse

logger = logging.getLogger(__name__)

class ShortTermMemory:
    """DragonflyDB-compatible Redis short-term memory store for ContextPacks and ReviewResponses."""

    def __init__(self, url: str) -> None:
        """
        Initialize the ShortTermMemory connection.

        Args:
            url: Redis connection URL (e.g. redis://localhost:6379/0).
        """
        self.url = url
        self.redis = redis.from_url(url, decode_responses=True)

    async def cache_context(self, pr_id: str, context_pack: ContextPack, ttl_seconds: int = 3600) -> None:
        """
        Cache a ContextPack object.

        Args:
            pr_id: Unique identifier for the PR.
            context_pack: ContextPack instance to cache.
            ttl_seconds: Time to live in seconds.
        """
        key = f"ctx:{pr_id}"
        try:
            data_json = context_pack.model_dump_json()
            await self.redis.set(key, data_json, ex=ttl_seconds)
            logger.info(f"Cached ContextPack for PR {pr_id} (TTL: {ttl_seconds}s)")
        except Exception as e:
            logger.error(f"Failed to cache ContextPack for PR {pr_id}: {e}", exc_info=True)

    async def get_context(self, pr_id: str) -> Optional[ContextPack]:
        """
        Retrieve a cached ContextPack object.

        Args:
            pr_id: Unique identifier for the PR.

        Returns:
            The cached ContextPack instance, or None.
        """
        key = f"ctx:{pr_id}"
        try:
            data_json = await self.redis.get(key)
            if data_json:
                return ContextPack.model_validate_json(data_json)
        except Exception as e:
            logger.error(f"Failed to retrieve ContextPack for PR {pr_id}: {e}", exc_info=True)
        return None

    async def cache_review(self, pr_id: str, review: ReviewResponse, ttl_seconds: int = 86400) -> None:
        """
        Cache a ReviewResponse object.

        Args:
            pr_id: Unique identifier for the PR.
            review: ReviewResponse instance to cache.
            ttl_seconds: Time to live in seconds.
        """
        key = f"rev:{pr_id}"
        try:
            data_json = review.model_dump_json()
            await self.redis.set(key, data_json, ex=ttl_seconds)
            logger.info(f"Cached ReviewResponse for PR {pr_id} (TTL: {ttl_seconds}s)")
        except Exception as e:
            logger.error(f"Failed to cache ReviewResponse for PR {pr_id}: {e}", exc_info=True)

    async def get_review(self, pr_id: str) -> Optional[ReviewResponse]:
        """
        Retrieve a cached ReviewResponse object.

        Args:
            pr_id: Unique identifier for the PR.

        Returns:
            The cached ReviewResponse instance, or None.
        """
        key = f"rev:{pr_id}"
        try:
            data_json = await self.redis.get(key)
            if data_json:
                return ReviewResponse.model_validate_json(data_json)
        except Exception as e:
            logger.error(f"Failed to retrieve ReviewResponse for PR {pr_id}: {e}", exc_info=True)
        return None

    async def invalidate(self, pr_id: str) -> None:
        """
        Delete all cached keys associated with the PR ID.

        Args:
            pr_id: Unique identifier for the PR.
        """
        keys = [f"ctx:{pr_id}", f"rev:{pr_id}"]
        try:
            await self.redis.delete(*keys)
            logger.info(f"Invalidated short term memory keys for PR {pr_id}")
        except Exception as e:
            logger.error(f"Failed to invalidate keys for PR {pr_id}: {e}", exc_info=True)

    async def health_check(self) -> bool:
        """
        Perform a ping request to verify connection health.

        Returns:
            True if healthy, False otherwise.
        """
        try:
            return await self.redis.ping()
        except Exception:
            return False

    async def close(self) -> None:
        """
        Close the Redis connection pool.
        """
        await self.redis.close()
