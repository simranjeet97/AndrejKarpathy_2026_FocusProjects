"""Reflection agent condition — explicit reflection step on failure."""

from __future__ import annotations

import time

from agent_learning.agent.base import AgentBase, AgentResult
from agent_learning.environment.runner import CodeExtractor
from agent_learning.environment.task import Task
from agent_learning.models.interface import Message, ModelInterface, TokenBudget


class ReflectionAgent(AgentBase):
    """Reflection agent condition.

    Adds explicit reflection after test failures.
    Reflection state is NOT persisted between independent tasks.
    """

    def __init__(self, model: ModelInterface) -> None:
        super().__init__(model=model, condition_name="reflection")

    def solve(self, task: Task, budget: TokenBudget | None = None) -> AgentResult:
        budget = budget or TokenBudget()
        start_time = time.monotonic()
        attempts = 0
        final_code = task.starter_code
        success = False
        reflections: list[str] = []

        messages = [
            Message(
                role="system",
                content="You are a coding assistant. Write clear Python code to solve the task. Always return code in ```python ... ``` blocks.",
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

            # Failure occurred -> Explicit Reflection Step
            if budget.can_call_model:
                reflect_msg = [
                    *messages,
                    Message(
                        role="user",
                        content=(
                            f"The solution failed tests:\n{feedback.to_prompt_str()}\n\n"
                            "Please reflect carefully on what went wrong, root cause, and how to fix it."
                        ),
                    ),
                ]
                reflect_resp = self.model.complete(reflect_msg)
                budget.record_model_call(reflect_resp)
                reflections.append(reflect_resp.content)

                messages.append(
                    Message(
                        role="user",
                        content=f"Test Failures:\n{feedback.to_prompt_str()}\n\nYour Reflection:\n{reflect_resp.content}\n\nNow write a revised solution in ```python ... ```.",
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
            reflection_output="\n---\n".join(reflections) if reflections else None,
        )
