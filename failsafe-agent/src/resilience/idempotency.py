import functools
import pickle
import time
from typing import Callable, Any, TypeVar, cast
import redis.asyncio as aioredis
import structlog

from src.config import settings

logger = structlog.get_logger()
F = TypeVar("F", bound=Callable[..., Any])


def idempotent(key_fn: Callable[..., str], ttl: int = 86400) -> Callable[[F], F]:
    """
    Decorator to enforce idempotency on an async operation.
    Stores and retrieves results (including raised exceptions) using Redis.
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Resolve Redis client
            # 1. From kwargs
            redis_client = kwargs.get("redis_client")
            # 2. Or from first arg (self/cls)
            if not redis_client and args:
                redis_client = getattr(args[0], "redis", None) or getattr(args[0], "redis_client", None)
            # 3. Or instantiate from settings
            is_local_client = False
            if not redis_client:
                redis_client = aioredis.from_url(settings.REDIS_URL)
                is_local_client = True

            try:
                # Generate unique idempotency key
                key = key_fn(**kwargs)
                redis_key = f"idempotency:{key}"
            except Exception as e:
                logger.error("Failed to generate idempotency key", error=str(e))
                if is_local_client:
                    await redis_client.close()
                return await func(*args, **kwargs)

            try:
                # Try to retrieve cached result
                cached_data = await redis_client.get(redis_key)
                if cached_data:
                    try:
                        entry = pickle.loads(cached_data)
                        logger.info(
                            "Idempotency cache hit",
                            action="idempotency_hit",
                            key=key,
                            cached_at=entry.get("cached_at"),
                        )
                        result_or_exc = entry.get("result")
                        if isinstance(result_or_exc, BaseException):
                            raise result_or_exc
                        return result_or_exc
                    except Exception as e:
                        if isinstance(e, BaseException) and not isinstance(e, KeyError):
                            # Re-raise the cached exception
                            raise e
                        logger.error("Corrupted cache entry found", key=key, error=str(e))

                # First call: execute operation
                try:
                    result = await func(*args, **kwargs)
                    cache_entry = {
                        "result": result,
                        "cached_at": time.time(),
                    }
                    await redis_client.set(redis_key, pickle.dumps(cache_entry), ex=ttl)
                    return result
                except Exception as exc:
                    # Cache the exception to re-raise it on repeat calls
                    cache_entry = {
                        "result": exc,
                        "cached_at": time.time(),
                    }
                    await redis_client.set(redis_key, pickle.dumps(cache_entry), ex=ttl)
                    raise exc
            finally:
                if is_local_client:
                    await redis_client.close()

        return cast(F, wrapper)
    return decorator
