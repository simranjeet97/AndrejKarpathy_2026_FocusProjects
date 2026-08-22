"""Baseline agent condition — standard coding agent without state retention."""

from __future__ import annotations

import time

from agent_learning.agent.base import AgentBase, AgentResult
from agent_learning.environment.runner import CodeExtractor
from agent_learning.environment.task import Task
from agent_learning.models.interface import Message, ModelInterface, TokenBudget


class BaselineAgent(AgentBase):
    """Baseline agent condition.

    Standard code-run-retry loop. Retains no information between tasks.
    """

    def __init__(self, model: ModelInterface) -> None:
        super().__init__(model=model, condition_name="baseline")

    def solve(self, task: Task, budget: TokenBudget | None = None) -> AgentResult:
        budget = budget or TokenBudget()
        start_time = time.monotonic()
        attempts = 0
        final_code = task.starter_code
        success = False

        messages = [
            Message(
                role="system",
                content="You are a coding assistant. Write clear Python code to solve the user's task. Always return code in ```python ... ``` blocks.",
            ),
            Message(
                role="user",
                content=f"Task ID: {task.id}\nTask Specification:\n{task.specification}\n\nStarter Code:\n{task.starter_code}\n\nVisible Tests:\n{task.visible_tests}",
            ),
        ]

        while budget.can_call_model and budget.can_run_tests:
            attempts += 1
            response = self.model.complete(messages)
            budget.record_model_call(response)

            code = CodeExtractor.extract(response.content)
            if code:
                final_code = code

            messages.append(Message(role="assistant", content=response.content))

            # Run visible tests
            budget.record_test_run()
            feedback = self.test_executor.run_visible_tests(task, final_code)

            if feedback.success:
                success = True
                break

            # Feedback prompt for retry
            messages.append(
                Message(
                    role="user",
                    content=f"Your solution failed tests:\n{feedback.to_prompt_str()}\nPlease fix your code.",
                )
            )

        elapsed = time.monotonic() - start_time
        return AgentResult(
            task_id=task.id,
            condition=self.condition_name,
            success=success,
            final_code=final_code,
            attempts=attempts,
            model_calls=budget.model_calls,
            input_tokens=budget.input_tokens,
            output_tokens=budget.output_tokens,
            total_tokens=budget.total_tokens,
            test_executions=budget.test_runs,
            elapsed_seconds=elapsed,
        )
