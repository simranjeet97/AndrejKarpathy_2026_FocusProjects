import asyncio
import functools
import random
from typing import Callable, Any, Type, Tuple, TypeVar, cast

import httpx
import structlog

from src.observability.metrics import RETRIES_TOTAL

logger = structlog.get_logger()


class RateLimitError(Exception):
    """Custom exception raised when requests are rate limited."""
    pass


F = TypeVar("F", bound=Callable[..., Any])


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retryable_exceptions: Tuple[Type[BaseException], ...] = (httpx.TimeoutException, RateLimitError),
) -> Callable[[F], F]:
    """
    Decorator that retries an async function with exponential backoff and full jitter.
    
    Formula:
        delay = min(max_delay, base_delay * 2 ** (attempt - 1))
        actual_delay = random.uniform(0, delay)
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = Exception("Unknown error")
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt == max_attempts:
                        logger.error(
                            "Max retry attempts reached, raising exception",
                            func_name=getattr(func, "__name__", str(func)),
                            attempt=attempt,
                            exception_type=type(e).__name__,
                        )
                        break
                    
                    # Exponential backoff with full jitter
                    backoff = min(max_delay, base_delay * (2 ** (attempt - 1)))
                    actual_delay = random.uniform(0, backoff)
                    
                    logger.warning(
                        "Retrying async function call after exception",
                        func_name=getattr(func, "__name__", str(func)),
                        attempt=attempt,
                        max_attempts=max_attempts,
                        exception_type=type(e).__name__,
                        delay_seconds=actual_delay,
                    )
                    
                    # Increment Prometheus retry counter
                    RETRIES_TOTAL.labels(
                        operation=getattr(func, "__name__", str(func)),
                        attempt_number=str(attempt),
                    ).inc()
                    
                    await asyncio.sleep(actual_delay)
            
            raise last_exception
        return cast(F, wrapper)
    return decorator

