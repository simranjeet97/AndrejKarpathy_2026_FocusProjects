import datetime
import time
import uuid
from typing import Any, NamedTuple, Optional
import structlog
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger()


class RateLimitResult(NamedTuple):
    allowed: bool
    remaining: int
    reset_at: datetime.datetime


async def check_rate_limit(
    customer_id: str,
    action: str,
    max_calls: int,
    window_seconds: int,
    redis_client: Any,
) -> RateLimitResult:
    """
    Implements a sliding window rate limiter backed by Redis sorted sets (ZSET).
    """
    key = f"rl:{customer_id}:{action}"
    now = time.time()
    cutoff = now - window_seconds

    # Use pipeline to group operations atomically
    async with redis_client.pipeline(transaction=True) as pipe:
        # 1. Remove elements older than cutoff
        pipe.zremrangebyscore(key, "-inf", f"({cutoff}")
        # 2. Add current timestamp (append uuid suffix to avoid collisions in same microsecond)
        pipe.zadd(key, {f"{now}:{uuid.uuid4().hex[:4]}": now})
        # 3. Get count of elements in sorted set
        pipe.zcard(key)
        # 4. Fetch the oldest element in the window to compute exact reset time
        pipe.zrange(key, 0, 0, withscores=True)
        # 5. Set TTL on the key to avoid leaking keys in Redis
        pipe.expire(key, window_seconds)

        results = await pipe.execute()

    count = results[2]
    oldest_elements = results[3]

    if oldest_elements:
        # Reset occurs when the oldest score slides out of the window
        reset_timestamp = oldest_elements[0][1] + window_seconds
    else:
        reset_timestamp = now + window_seconds

    allowed = count <= max_calls
    remaining = max(0, max_calls - count)
    reset_at = datetime.datetime.fromtimestamp(reset_timestamp, tz=datetime.timezone.utc)

    return RateLimitResult(allowed=allowed, remaining=remaining, reset_at=reset_at)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware that enforces a sliding-window rate limit on conversation endpoints
    (10 conversations per hour) using 'X-Customer-ID' header.
    """
    async def dispatch(self, request: Request, call_next: Any) -> Response:
        customer_id = request.headers.get("X-Customer-ID")

        # Apply rate limits only to conversation endpoints
        if customer_id and request.url.path.startswith("/conversations"):
            redis_client = getattr(request.app.state, "redis_client", None)
            
            if redis_client:
                try:
                    res = await check_rate_limit(
                        customer_id=customer_id,
                        action="conversations",
                        max_calls=10,
                        window_seconds=3600,
                        redis_client=redis_client,
                    )
                    
                    if not res.allowed:
                        now_utc = datetime.datetime.now(datetime.timezone.utc)
                        retry_after = int((res.reset_at - now_utc).total_seconds())
                        retry_after = max(1, retry_after)
                        
                        logger.warn(
                            "Rate limit exceeded",
                            customer_id=customer_id,
                            action="conversations",
                            retry_after=retry_after,
                        )
                        
                        return JSONResponse(
                            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            content={
                                "error": "Too Many Requests",
                                "message": "Conversation creation rate limit exceeded (max 10/hour).",
                            },
                            headers={"Retry-After": str(retry_after)},
                        )
                except Exception as e:
                    # Fail open to preserve service availability if cache is offline
                    logger.error("Rate limit check failed, failing open", error=str(e))

        return await call_next(request)
