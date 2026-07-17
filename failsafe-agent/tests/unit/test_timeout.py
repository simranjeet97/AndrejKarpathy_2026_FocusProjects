import asyncio
import time
import pytest
from freezegun import freeze_time

from src.resilience.timeout import with_timeout, OperationTimeoutError, TimeoutBudget


@pytest.mark.asyncio
async def test_with_timeout_success() -> None:
    async def quick_task() -> str:
        return "done"
        
    res = await with_timeout(quick_task(), timeout_seconds=1.0, operation_name="quick")
    assert res == "done"


@pytest.mark.asyncio
async def test_with_timeout_exceeded() -> None:
    async def slow_task() -> None:
        await asyncio.sleep(10.0)
        
    with pytest.raises(OperationTimeoutError) as exc_info:
        await with_timeout(slow_task(), timeout_seconds=0.01, operation_name="slow")
        
    assert exc_info.value.operation_name == "slow"
    assert exc_info.value.timeout_seconds == 0.01


def test_timeout_budget_remaining() -> None:
    with freeze_time("2026-07-17T12:00:00Z") as frozen_time:
        budget = TimeoutBudget(total_seconds=30.0)
        assert budget.remaining() == 30.0
        
        # Advance time by 10 seconds
        frozen_time.tick(10.0)
        assert budget.remaining() == 20.0
        
        # Advance time past the budget
        frozen_time.tick(25.0)
        assert budget.remaining() == 0.0


def test_timeout_budget_sub_allocation() -> None:
    with freeze_time("2026-07-17T12:00:00Z") as frozen_time:
        budget = TimeoutBudget(total_seconds=40.0)
        
        # Tick 10 seconds, leaving 30 seconds
        frozen_time.tick(10.0)
        assert budget.remaining() == 30.0
        
        # Allocate half (0.5) of the remaining 30s -> 15s
        sub = budget.sub_budget(fraction=0.5)
        assert sub.remaining() == 15.0
        
        # Tick sub-budget 5 seconds, remaining in sub should be 10s
        frozen_time.tick(5.0)
        assert sub.remaining() == 10.0
        
        # Parent remaining budget should also track this elapsed time (30s - 5s = 25s)
        assert budget.remaining() == 25.0
