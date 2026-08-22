"""Workflow executor driving agent steps according to workflow configuration."""

from __future__ import annotations

from typing import Callable, Any
from agent_learning.workflow.schema import Workflow, WorkflowStep


class WorkflowExecutor:
    """Executes step handlers according to the active Workflow configuration."""

    def __init__(self, workflow: Workflow) -> None:
        self.workflow = workflow

    def execute(self, handlers: dict[WorkflowStep, Callable[[], Any]]) -> list[Any]:
        """Execute handlers matching steps in the workflow.

        Args:
            handlers: Dictionary mapping WorkflowStep to step functions.

        Returns:
            List of results from executed steps.
        """
        results = []
        for step in self.workflow.steps:
            if step in handlers:
                res = handlers[step]()
                results.append(res)
        return results
