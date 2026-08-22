"""Main experiment runner implementing the core experimental protocol."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from agent_learning.agent.base import AgentBase, AgentResult
from agent_learning.agent.baseline import BaselineAgent
from agent_learning.agent.memory import MemoryAgent
from agent_learning.agent.reflection import ReflectionAgent
from agent_learning.agent.workflow import WorkflowAgent
from agent_learning.environment.task import Task, load_all_tasks
from agent_learning.environment.tests import TestExecutor
from agent_learning.experiment.config import ExperimentConfig
from agent_learning.experiment.isolation import ExperimentIsolation
from agent_learning.experiment.phases import PhaseExecutor
from agent_learning.experiment.splits import DatasetSplits, generate_splits
from agent_learning.logging_config import ExperimentLogEntry, StructuredLogger
from agent_learning.memory.store import MemoryStore
from agent_learning.models.interface import ModelInterface
from agent_learning.models.local import LocalModelClient
from agent_learning.models.mock import MockModel
from agent_learning.workflow.schema import Workflow


class ExperimentRunner:
    """Orchestrates the 4 agent conditions across all experimental phases."""

    def __init__(self, config: ExperimentConfig) -> None:
        self.config = config
        self.experiment_id = f"{config.experiment.name}_{uuid.uuid4().hex[:6]}"
        self.logger = StructuredLogger(
            log_dir=Path(config.output.logs_dir),
            experiment_id=self.experiment_id,
            format=config.logging.format,
            level=config.logging.level,
        )
        self.isolation = ExperimentIsolation(config.output.raw_dir)

    def _init_model(self) -> ModelInterface:
        if self.config.model.provider == "mock":
            return MockModel(model_name=self.config.model.model)
        return LocalModelClient(
            endpoint=self.config.model.endpoint,
            model=self.config.model.model,
        )

    def run(self) -> None:
        """Run full experiment protocol across configured runs and conditions."""
        tasks_dir = Path(self.config.dataset.tasks_dir)
        all_tasks = load_all_tasks(tasks_dir)
        splits = generate_splits(all_tasks, seed=self.config.experiment.seed)
        splits.save(Path(self.config.dataset.splits_dir))

        task_map = {t.id: t for t in all_tasks}

        feedback_tasks = [task_map[tid] for tid in splits.feedback_ids if tid in task_map]
        held_out_tasks = [task_map[tid] for tid in splits.test_ids if tid in task_map]
        cross_family_tasks = [
            task_map[tid] for tid in splits.cross_family_ids if tid in task_map
        ]
        regression_tasks = [
            task_map[tid] for tid in splits.regression_ids if tid in task_map
        ]

        for run_idx in range(1, self.config.experiment.runs + 1):
            for cond_name in self.config.experiment.conditions:
                self.logger.log_event(
                    "condition_start", condition=cond_name, run_idx=run_idx
                )
                self._run_condition(
                    condition_name=cond_name,
                    run_idx=run_idx,
                    feedback_tasks=feedback_tasks,
                    held_out_tasks=held_out_tasks,
                    cross_family_tasks=cross_family_tasks,
                    regression_tasks=regression_tasks,
                )

    def run_single_task(self, task_id: str) -> None:
        """Run a single task through baseline agent."""
        tasks_dir = Path(self.config.dataset.tasks_dir)
        all_tasks = load_all_tasks(tasks_dir)
        task = next((t for t in all_tasks if t.id == task_id), None)
        if not task:
            print(f"Task {task_id} not found.")
            return

        model = self._init_model()
        agent = BaselineAgent(model=model)
        res = agent.solve(task)
        print(f"Single task {task_id} result: {'PASS' if res.success else 'FAIL'}")

    def _run_condition(
        self,
        condition_name: str,
        run_idx: int,
        feedback_tasks: list[Task],
        held_out_tasks: list[Task],
        cross_family_tasks: list[Task],
        regression_tasks: list[Task],
    ) -> None:
        model = self._init_model()
        cond_dir = self.isolation.create_condition_dir(condition_name, run_idx)

        # Initialize condition state
        mem_store = MemoryStore(storage_file=cond_dir / "memory_store.json")
        workflow = Workflow()

        agent: AgentBase
        if condition_name == "baseline":
            agent = BaselineAgent(model=model)
        elif condition_name == "reflection":
            agent = ReflectionAgent(model=model)
        elif condition_name == "memory":
            agent = MemoryAgent(model=model, memory_store=mem_store)
        elif condition_name == "workflow":
            agent = WorkflowAgent(model=model, workflow=workflow)
        else:
            raise ValueError(f"Unknown condition: {condition_name}")

        # Phase 1: Feedback phase
        fb_results = PhaseExecutor.run_phase(
            agent, feedback_tasks, phase_name="feedback"
        )
        self._save_results(fb_results, "feedback", condition_name, run_idx)

        # Phase 2: CRITICAL - Remove feedback signal and original task conversations!
        # Memory/Workflow agents retain ONLY external state (memory store or workflow config)
        if condition_name == "memory":
            agent = MemoryAgent(model=model, memory_store=mem_store)
        elif condition_name == "workflow":
            agent = WorkflowAgent(model=model, workflow=workflow)
        elif condition_name == "reflection":
            agent = ReflectionAgent(model=model)
        else:
            agent = BaselineAgent(model=model)

        # Phase 3: Held-out evaluation
        ho_results = PhaseExecutor.run_phase(
            agent, held_out_tasks, phase_name="held_out"
        )
        self._save_results(ho_results, "held_out", condition_name, run_idx)

        # Phase 4: Cross family evaluation
        cf_results = PhaseExecutor.run_phase(
            agent, cross_family_tasks, phase_name="cross_family"
        )
        self._save_results(cf_results, "cross_family", condition_name, run_idx)

        # Phase 5: Regression evaluation
        reg_results = PhaseExecutor.run_phase(
            agent, regression_tasks, phase_name="regression"
        )
        self._save_results(reg_results, "regression", condition_name, run_idx)

    def _save_results(
        self,
        results: list[AgentResult],
        phase: str,
        condition: str,
        run_idx: int,
    ) -> None:
        out_file = (
            Path(self.config.output.raw_dir)
            / f"run_{run_idx}"
            / condition
            / f"{phase}_results.json"
        )
        out_file.parent.mkdir(parents=True, exist_ok=True)
        data = [r.__dict__ for r in results]
        with open(out_file, "w") as f:
            json.dump(data, f, indent=2)

        # Log entries
        for r in results:
            entry = ExperimentLogEntry(
                experiment_id=self.experiment_id,
                condition=condition,
                task_id=r.task_id,
                task_family="",
                seed=self.config.experiment.seed,
                model=self.config.model.model,
                attempt=r.attempts,
                model_calls=r.model_calls,
                input_tokens=r.input_tokens,
                output_tokens=r.output_tokens,
                total_tokens=r.total_tokens,
                test_executions=r.test_executions,
                success=r.success,
                reflection_output=r.reflection_output,
                memory_written=r.memories_written,
                memory_retrieved=r.memories_retrieved,
                workflow_modification=r.workflow_modification,
                elapsed_seconds=r.elapsed_seconds,
                phase=phase,
            )
            self.logger.log_entry(entry)
