"""Experiment phase abstractions (Feedback, Evaluation, Retention)."""

from __future__ import annotations

from typing import Sequence
from agent_learning.agent.base import AgentBase, AgentResult
from agent_learning.environment.task import Task
from agent_learning.models.interface import TokenBudget


class PhaseExecutor:
    """Executes a list of tasks for a given agent condition and phase."""

    @staticmethod
    def run_phase(
        agent: AgentBase,
        tasks: Sequence[Task],
        phase_name: str,
        max_calls_per_task: int = 20,
        max_tokens_per_task: int = 120000,
        max_tests_per_task: int = 30,
    ) -> list[AgentResult]:
        results = []
        for task in tasks:
            budget = TokenBudget(
                max_model_calls=max_calls_per_task,
                max_total_tokens=max_tokens_per_task,
                max_test_runs=max_tests_per_task,
            )
            res = agent.solve(task, budget)
            results.append(res)
        return results
