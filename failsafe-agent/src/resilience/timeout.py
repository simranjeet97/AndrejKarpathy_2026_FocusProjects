import asyncio
import time
from typing import Any, Coroutine
import structlog

logger = structlog.get_logger()


class OperationTimeoutError(Exception):
    """Exception raised when an operation exceeds its allocated timeout."""
    def __init__(self, operation_name: str, timeout_seconds: float) -> None:
        super().__init__(f"Operation '{operation_name}' timed out after {timeout_seconds} seconds")
        self.operation_name = operation_name
        self.timeout_seconds = timeout_seconds


async def with_timeout(
    coro: Coroutine[Any, Any, Any],
    timeout_seconds: float,
    operation_name: str,
) -> Any:
    """Wraps asyncio.wait_for, logging structured records and raising custom exceptions on timeout."""
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except (asyncio.TimeoutError, TimeoutError) as e:
        logger.error(
            "Operation timed out",
            operation=operation_name,
            timeout=timeout_seconds,
            action="timed_out",
        )
        raise OperationTimeoutError(operation_name, timeout_seconds) from e


class TimeoutBudget:
    """Tracks a total time budget for a request, allowing allocation of fractional sub-budgets."""
    def __init__(self, total_seconds: float = 30.0) -> None:
        self.total_seconds = total_seconds
        self.start_time = time.time()

    def remaining(self) -> float:
        """Returns the remaining time in seconds, floored at 0.0."""
        elapsed = time.time() - self.start_time
        return max(0.0, self.total_seconds - elapsed)

    def sub_budget(self, fraction: float) -> "TimeoutBudget":
        """Allocates a portion (fraction between 0.0 and 1.0) of the current remaining time budget."""
        current_remaining = self.remaining()
        allocated_seconds = current_remaining * fraction
        return TimeoutBudget(total_seconds=allocated_seconds)
