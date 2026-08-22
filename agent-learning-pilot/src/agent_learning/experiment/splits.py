"""Deterministic split generation and management."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from agent_learning.environment.task import Task, TaskFamily


@dataclass
class DatasetSplits:
    feedback_ids: list[str]
    validation_ids: list[str]
    test_ids: list[str]
    cross_family_ids: list[str]
    regression_ids: list[str]

    def save(self, splits_dir: Path | str) -> None:
        splits_dir = Path(splits_dir)
        splits_dir.mkdir(parents=True, exist_ok=True)
        mapping = {
            "feedback.json": self.feedback_ids,
            "validation.json": self.validation_ids,
            "test.json": self.test_ids,
            "cross_family.json": self.cross_family_ids,
            "regression.json": self.regression_ids,
        }
        for filename, ids in mapping.items():
            with open(splits_dir / filename, "w") as f:
                json.dump({"task_ids": ids}, f, indent=2)

    @classmethod
    def load(cls, splits_dir: Path | str) -> DatasetSplits:
        splits_dir = Path(splits_dir)

        def read_ids(filename: str) -> list[str]:
            p = splits_dir / filename
            if not p.exists():
                return []
            with open(p, "r") as f:
                return json.load(f).get("task_ids", [])

        return cls(
            feedback_ids=read_ids("feedback.json"),
            validation_ids=read_ids("validation.json"),
            test_ids=read_ids("test.json"),
            cross_family_ids=read_ids("cross_family.json"),
            regression_ids=read_ids("regression.json"),
        )


def generate_splits(tasks: Sequence[Task], seed: int = 42) -> DatasetSplits:
    """Generate deterministic train/eval/test splits from task list."""
    rng = random.Random(seed)

    # Group by family
    by_family: dict[TaskFamily, list[Task]] = {f: [] for f in TaskFamily}
    for t in tasks:
        by_family[t.family].append(t)

    # Sort deterministically
    for f in by_family:
        by_family[f].sort(key=lambda t: t.id)
        rng.shuffle(by_family[f])

    # Assign primary feedback family (e.g. data_manipulation or algorithms)
    primary_family = TaskFamily.DATA_MANIPULATION
    cross_family = TaskFamily.ALGORITHMS

    primary_tasks = by_family[primary_family]
    cross_tasks = by_family[cross_family]
    other_tasks = []
    for f, t_list in by_family.items():
        if f not in (primary_family, cross_family):
            other_tasks.extend(t_list)

    # Split primary into feedback, validation, test, regression
    n = len(primary_tasks)
    n_feedback = max(1, int(n * 0.4))
    n_val = max(1, int(n * 0.2))
    n_test = max(1, int(n * 0.2))

    feedback_ids = [t.id for t in primary_tasks[:n_feedback]]
    val_ids = [t.id for t in primary_tasks[n_feedback : n_feedback + n_val]]
    test_ids = [
        t.id for t in primary_tasks[n_feedback + n_val : n_feedback + n_val + n_test]
    ]
    reg_ids = [t.id for t in primary_tasks[n_feedback + n_val + n_test :]]

    cross_ids = [t.id for t in cross_tasks]

    return DatasetSplits(
        feedback_ids=feedback_ids,
        validation_ids=val_ids,
        test_ids=test_ids,
        cross_family_ids=cross_ids,
        regression_ids=reg_ids,
    )
