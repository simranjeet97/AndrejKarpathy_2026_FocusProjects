"""Declarative workflow schemas and constraints for the Workflow condition."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class WorkflowStep(str, Enum):
    """Allowed operations in agent workflow."""

    INSPECT_TESTS = "inspect_tests"
    IDENTIFY_EDGE_CASES = "identify_edge_cases"
    PLAN = "plan"
    CODE = "code"
    TEST = "test"
    REGRESSION_CHECK = "regression_check"
    REVIEW_ERRORS = "review_errors"
    SIMPLIFY = "simplify"


DEFAULT_WORKFLOW = [
    WorkflowStep.PLAN,
    WorkflowStep.CODE,
    WorkflowStep.TEST,
]


@dataclass
class Workflow:
    """Sequence of steps representing an agent's problem-solving workflow."""

    steps: list[WorkflowStep] = field(default_factory=lambda: list(DEFAULT_WORKFLOW))

    def validate(self) -> tuple[bool, str | None]:
        """Validate workflow safety constraints.

        Must contain CODE and TEST, max 8 steps.
        """
        if WorkflowStep.CODE not in self.steps:
            return False, "Workflow must include 'code' step"
        if WorkflowStep.TEST not in self.steps:
            return False, "Workflow must include 'test' step"
        if len(self.steps) > 8:
            return False, "Workflow max steps exceeded (limit 8)"
        return True, None

    def to_list(self) -> list[str]:
        return [step.value for step in self.steps]

    @classmethod
    def from_list(cls, step_names: list[str]) -> Workflow:
        steps = []
        for name in step_names:
            try:
                steps.append(WorkflowStep(name))
            except ValueError:
                pass
        wf = cls(steps=steps)
        valid, msg = wf.validate()
        if not valid:
            return cls(steps=list(DEFAULT_WORKFLOW))
        return wf
