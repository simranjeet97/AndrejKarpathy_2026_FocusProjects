"""Workflow modification agent condition — modifies execution steps across tasks."""

from __future__ import annotations

import time

from agent_learning.agent.base import AgentBase, AgentResult
from agent_learning.environment.runner import CodeExtractor
from agent_learning.environment.task import Task
from agent_learning.models.interface import Message, ModelInterface, TokenBudget
from agent_learning.workflow.executor import WorkflowExecutor
from agent_learning.workflow.mutation import WorkflowMutator
from agent_learning.workflow.schema import Workflow, WorkflowStep


class WorkflowAgent(AgentBase):
    """Workflow agent condition.

    Allowed to propose modifications to its execution workflow after feedback.
    Workflow sequence persists across tasks.
    """

    def __init__(
        self,
        model: ModelInterface,
        workflow: Workflow | None = None,
    ) -> None:
        super().__init__(model=model, condition_name="workflow")
        self.workflow = workflow or Workflow()

    def solve(self, task: Task, budget: TokenBudget | None = None) -> AgentResult:
        budget = budget or TokenBudget()
        start_time = time.monotonic()
        attempts = 0
        final_code = task.starter_code
        success = False
        workflow_modification: str | None = None

        wf_str = ", ".join(self.workflow.to_list())

        messages = [
            Message(
                role="system",
                content=f"You are a coding assistant following this workflow sequence: [{wf_str}]. Follow each step in order.",
            ),
            Message(
                role="user",
                content=f"Task ID: {task.id}\nTask Specification:\n{task.specification}\n\nStarter Code:\n{task.starter_code}\n\nVisible Tests:\n{task.visible_tests}",
            ),
        ]

        feedback_summary = ""

        while budget.can_call_model and budget.can_run_tests:
            attempts += 1
            response = self.model.complete(messages)
            budget.record_model_call(response)

            code = CodeExtractor.extract(response.content)
            if code:
                final_code = code

            messages.append(Message(role="assistant", content=response.content))

            budget.record_test_run()
            feedback = self.test_executor.run_visible_tests(task, final_code)
            feedback_summary = feedback.to_prompt_str()

            if feedback.success:
                success = True
                break

            messages.append(
                Message(
                    role="user",
                    content=f"Solution failed tests:\n{feedback_summary}\nPlease fix code following your workflow.",
                )
            )

        # Propose workflow modification after task completion/attempt
        if budget.can_call_model:
            proposal_prompt = [
                Message(
                    role="system",
                    content=(
                        "You can propose a workflow change. Allowed steps: "
                        "inspect_tests, identify_edge_cases, plan, code, test, regression_check, review_errors, simplify.\n"
                        "Return JSON with 'proposed_workflow' (list of step strings)."
                    ),
                ),
                Message(
                    role="user",
                    content=f"Current Workflow: {self.workflow.to_list()}\nLast Task Result: {feedback_summary}\nPropose workflow modifications if needed.",
                ),
            ]
            prop_resp = self.model.complete(proposal_prompt)
            budget.record_model_call(prop_resp)

            new_wf, accepted, reason = WorkflowMutator.parse_and_apply(
                prop_resp.content, self.workflow
            )
            if accepted:
                self.workflow = new_wf
                workflow_modification = f"Updated workflow to: {self.workflow.to_list()}"

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
            workflow_modification=workflow_modification,
        )
