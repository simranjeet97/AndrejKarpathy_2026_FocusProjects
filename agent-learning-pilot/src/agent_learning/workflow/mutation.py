"""Constrained workflow mutator for proposing and validating workflow changes."""

from __future__ import annotations

import json
from typing import Any
from agent_learning.workflow.schema import Workflow, WorkflowStep, DEFAULT_WORKFLOW


class WorkflowMutator:
    """Handles parsing and validating workflow modification proposals."""

    @staticmethod
    def parse_and_apply(
        proposal_text: str, current_workflow: Workflow
    ) -> tuple[Workflow, bool, str]:
        """Parse proposal JSON and update workflow if valid.

        Args:
            proposal_text: Raw model output containing proposal JSON.
            current_workflow: Active workflow before modification.

        Returns:
            Tuple of (new_workflow, accepted, reason_message).
        """
        try:
            # Look for JSON structure
            start_idx = proposal_text.find("{")
            end_idx = proposal_text.rfind("}") + 1
            if start_idx == -1 or end_idx <= start_idx:
                return current_workflow, False, "No JSON found in proposal text"

            json_str = proposal_text[start_idx:end_idx]
            data = json.loads(json_str)

            raw_steps = data.get("proposed_workflow") or data.get("steps")
            if not isinstance(raw_steps, list):
                return current_workflow, False, "'proposed_workflow' must be a list of step strings"

            # Parse steps
            new_steps: list[WorkflowStep] = []
            for s in raw_steps:
                try:
                    new_steps.append(WorkflowStep(s.lower().strip()))
                except ValueError:
                    pass

            candidate = Workflow(steps=new_steps)
            valid, msg = candidate.validate()
            if not valid:
                return current_workflow, False, f"Validation failed: {msg}"

            return candidate, True, "Workflow modification accepted"

        except Exception as e:
            return current_workflow, False, f"Error parsing proposal: {str(e)}"
