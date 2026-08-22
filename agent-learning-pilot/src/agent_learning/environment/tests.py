"""Test execution and result parsing.

Wraps pytest execution with structured result extraction
for use by the agent loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agent_learning.environment.runner import TaskRunner
from agent_learning.environment.task import Task, TaskResult


@dataclass
class TestFeedback:
    """Structured feedback from running tests.

    This is what agents receive after attempting a solution.
    It contains enough information to diagnose failures without
    leaking hidden test details.
    """

    success: bool
    tests_passed: int
    tests_failed: int
    tests_total: int
    error_summary: str
    visible_output: str

    @classmethod
    def from_result(cls, result: TaskResult, include_output: bool = True) -> "TestFeedback":
        """Create feedback from a task result.

        Args:
            result: Raw TaskResult from runner.
            include_output: Whether to include stdout/stderr (False for hidden tests).

        Returns:
            TestFeedback with structured information.
        """
        if include_output:
            # Truncate long output
            visible = result.stderr[:1500] if result.stderr else result.stdout[:1500]
        else:
            visible = ""

        # Create a concise error summary
        if result.success:
            summary = f"All {result.tests_total} tests passed."
        elif result.error:
            summary = f"Execution error: {result.error}"
        else:
            summary = (
                f"{result.tests_failed}/{result.tests_total} tests failed. "
                f"{result.tests_passed} passed."
            )

        return cls(
            success=result.success,
            tests_passed=result.tests_passed,
            tests_failed=result.tests_failed,
            tests_total=result.tests_total,
            error_summary=summary,
            visible_output=visible,
        )

    def to_prompt_str(self) -> str:
        """Format feedback for inclusion in a prompt.

        This is what the agent sees after running tests.
        """
        lines = [
            f"Test Results: {'PASS' if self.success else 'FAIL'}",
            f"  Passed: {self.tests_passed}/{self.tests_total}",
        ]
        if not self.success:
            lines.append(f"  Summary: {self.error_summary}")
            if self.visible_output:
                lines.append(f"  Output:\n{self.visible_output}")
        return "\n".join(lines)


class TestExecutor:
    """Orchestrates test execution for the agent loop.

    Manages visible vs hidden test runs and provides structured
    feedback to agents.
    """

    def __init__(self, timeout: int = 30) -> None:
        self.runner = TaskRunner(timeout=timeout)

    def run_visible_tests(self, task: Task, solution_code: str) -> TestFeedback:
        """Run visible tests and return agent-readable feedback.

        This is used during the agent's solve loop — the agent
        can see these results and iterate.

        Args:
            task: The task being solved.
            solution_code: Generated Python code.

        Returns:
            TestFeedback for the agent.
        """
        result = self.runner.run_solution(
            task=task,
            solution_code=solution_code,
            test_code=task.visible_tests,
            use_hidden_tests=False,
        )
        return TestFeedback.from_result(result, include_output=True)

    def run_hidden_tests(self, task: Task, solution_code: str) -> TaskResult:
        """Run hidden tests for final evaluation.

        Hidden tests determine the official task result.
        Output is not shown to the agent.

        Args:
            task: The task being solved.
            solution_code: Generated Python code.

        Returns:
            TaskResult (not TestFeedback — full details for evaluation).
        """
        return self.runner.run_solution(
            task=task,
            solution_code=solution_code,
            test_code=task.hidden_tests,
            use_hidden_tests=True,
        )
