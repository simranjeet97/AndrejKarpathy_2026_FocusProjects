"""Unit tests for task loading and validation."""

import pytest
from pathlib import Path
from agent_learning.environment.task import load_all_tasks, load_task, TaskFamily

def test_load_all_tasks():
    tasks = load_all_tasks(Path("data/tasks"))
    assert len(tasks) == 48

def test_task_families():
    tasks = load_all_tasks(Path("data/tasks"))
    families = {t.family for t in tasks}
    assert len(families) == 4
    assert TaskFamily.DATA_MANIPULATION in families
