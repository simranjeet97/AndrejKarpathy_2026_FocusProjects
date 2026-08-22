"""Task definitions, loading, and validation.

Every task has a unique ID, family classification, difficulty,
natural-language specification, starter code, visible tests,
hidden tests, and execution metadata.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class TaskFamily(str, Enum):
    """Families of coding tasks for the experiment."""

    DATA_MANIPULATION = "data_manipulation"
    ALGORITHMS = "algorithms"
    DEBUGGING = "debugging"
    SOFTWARE_ENGINEERING = "software_engineering"


class TaskDifficulty(str, Enum):
    """Task difficulty levels."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


@dataclass
class Task:
    """A single coding task in the benchmark.

    Each task is self-contained with specification, starter code,
    and both visible and hidden test suites.
    """

    id: str
    family: TaskFamily
    difficulty: TaskDifficulty
    title: str
    specification: str
    starter_code: str
    visible_tests: str
    hidden_tests: str
    timeout_seconds: int = 30
    expected_command: str = "pytest"

    @property
    def family_prefix(self) -> str:
        """Return the two-letter family prefix (e.g., 'dm', 'al')."""
        return self.id.split("_")[0]

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "family": self.family.value,
            "difficulty": self.difficulty.value,
            "title": self.title,
            "specification": self.specification,
            "starter_code": self.starter_code,
            "visible_tests": self.visible_tests,
            "hidden_tests": self.hidden_tests,
            "timeout_seconds": self.timeout_seconds,
            "expected_command": self.expected_command,
        }


@dataclass
class TaskResult:
    """Result of running a task solution against tests."""

    task_id: str
    success: bool
    tests_passed: int = 0
    tests_failed: int = 0
    tests_total: int = 0
    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    elapsed_seconds: float = 0.0
    error: str | None = None

    @property
    def pass_rate(self) -> float:
        """Fraction of tests passed."""
        if self.tests_total == 0:
            return 0.0
        return self.tests_passed / self.tests_total


def load_task(task_dir: Path) -> Task:
    """Load a single task from its directory.

    Expected structure:
        task_dir/
            task.json       # metadata
            starter.py      # starter code
            visible_tests.py
            hidden_tests.py

    Args:
        task_dir: Path to the task directory.

    Returns:
        A Task object.

    Raises:
        FileNotFoundError: If required files are missing.
        ValueError: If task metadata is invalid.
    """
    meta_path = task_dir / "task.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"Missing task.json in {task_dir}")

    with open(meta_path) as f:
        meta = json.load(f)

    # Read code files
    starter_path = task_dir / "starter.py"
    visible_path = task_dir / "visible_tests.py"
    hidden_path = task_dir / "hidden_tests.py"

    starter_code = starter_path.read_text() if starter_path.exists() else ""
    visible_tests = visible_path.read_text() if visible_path.exists() else ""
    hidden_tests = hidden_path.read_text() if hidden_path.exists() else ""

    try:
        family = TaskFamily(meta["family"])
    except (KeyError, ValueError) as e:
        raise ValueError(f"Invalid task family in {meta_path}: {e}")

    try:
        difficulty = TaskDifficulty(meta.get("difficulty", "medium"))
    except ValueError as e:
        raise ValueError(f"Invalid difficulty in {meta_path}: {e}")

    return Task(
        id=meta["id"],
        family=family,
        difficulty=difficulty,
        title=meta.get("title", meta["id"]),
        specification=meta["specification"],
        starter_code=starter_code,
        visible_tests=visible_tests,
        hidden_tests=hidden_tests,
        timeout_seconds=meta.get("timeout_seconds", 30),
        expected_command=meta.get("expected_command", "pytest"),
    )


def load_all_tasks(tasks_dir: Path) -> list[Task]:
    """Load all tasks from the dataset directory.

    Args:
        tasks_dir: Root directory containing task subdirectories.

    Returns:
        List of Task objects, sorted by ID.

    Raises:
        FileNotFoundError: If the tasks directory doesn't exist.
    """
    tasks_dir = Path(tasks_dir)
    if not tasks_dir.exists():
        raise FileNotFoundError(f"Tasks directory not found: {tasks_dir}")

    tasks = []
    for child in sorted(tasks_dir.iterdir()):
        if child.is_dir() and (child / "task.json").exists():
            tasks.append(load_task(child))

    return tasks


def load_tasks_by_ids(tasks_dir: Path, task_ids: list[str]) -> list[Task]:
    """Load specific tasks by their IDs.

    Args:
        tasks_dir: Root directory containing task subdirectories.
        task_ids: List of task IDs to load.

    Returns:
        List of Task objects.
    """
    tasks = []
    for task_id in task_ids:
        task_dir = tasks_dir / task_id
        if task_dir.exists():
            tasks.append(load_task(task_dir))
        else:
            raise FileNotFoundError(f"Task not found: {task_id} (looked in {task_dir})")
    return tasks
