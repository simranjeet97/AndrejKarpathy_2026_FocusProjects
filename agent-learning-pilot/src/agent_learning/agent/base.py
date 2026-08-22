"""Base agent class defining the core solving interface and budget tracking."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from agent_learning.environment.runner import CodeExtractor
from agent_learning.environment.task import Task
from agent_learning.environment.tests import TestExecutor, TestFeedback
from agent_learning.models.interface import Message, ModelInterface, TokenBudget


@dataclass
class AgentResult:
    """Result of an agent attempting a task."""

    task_id: str
    condition: str
    success: bool
    final_code: str
    attempts: int
    model_calls: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    test_executions: int
    elapsed_seconds: float
    reflection_output: str | None = None
    memories_written: list[str] = field(default_factory=list)
    memories_retrieved: list[str] = field(default_factory=list)
    workflow_modification: str | None = None
    error: str | None = None


class AgentBase:
    """Abstract base class for all four agent conditions."""

    def __init__(
        self,
        model: ModelInterface,
        condition_name: str,
        test_executor: TestExecutor | None = None,
    ) -> None:
        self.model = model
        self.condition_name = condition_name
        self.test_executor = test_executor or TestExecutor()

    def solve(
        self,
        task: Task,
        budget: TokenBudget | None = None,
    ) -> AgentResult:
        """Solve a task within the allocated compute budget."""
        raise NotImplementedError
