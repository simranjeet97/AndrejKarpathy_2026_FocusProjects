"""Unit tests for deterministic split generation."""

import pytest
from pathlib import Path
from agent_learning.environment.task import load_all_tasks
from agent_learning.experiment.splits import generate_splits

def test_split_reproducibility():
    tasks = load_all_tasks(Path("data/tasks"))
    s1 = generate_splits(tasks, seed=42)
    s2 = generate_splits(tasks, seed=42)
    assert s1.feedback_ids == s2.feedback_ids
    assert s1.test_ids == s2.test_ids
