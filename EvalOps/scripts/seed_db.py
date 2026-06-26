#!/usr/bin/env python3
"""
EvalOps — Database Seeder
Loads golden_datasets/example_dataset.json and inserts all tasks into the SQLite database.
"""

import os
import sys
import json
from typing import List, Dict, Any

# Ensure the project root is on PYTHONPATH so evalops can be imported
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from evalops.config import get_settings
from evalops.storage import SQLiteStorage
from evalops.models import EvalTask


def load_golden_dataset(filepath: str) -> List[Dict[str, Any]]:
    """
    Load golden dataset file from the specified JSON filepath.

    Args:
        filepath (str): Path to the dataset JSON file.

    Returns:
        List[Dict[str, Any]]: List of task definitions.
    """
    if not os.path.exists(filepath):
        print(f"✗ Dataset file not found: {filepath}")
        sys.exit(1)

    with open(filepath, "r") as f:
        data = json.load(f)

    if not isinstance(data, list):
        print(f"✗ Expected a JSON array in {filepath}, got {type(data).__name__}")
        sys.exit(1)

    return data


def seed_database(dataset_path: str = None) -> None:
    """
    Initialize SQLite database and seed it with tasks from the golden dataset.

    Args:
        dataset_path (str, optional): Path to the dataset file.
            Defaults to golden_datasets/example_dataset.json relative to project root.
    """
    if dataset_path is None:
        dataset_path = os.path.join(project_root, "golden_datasets", "example_dataset.json")

    # Initialize storage
    storage = SQLiteStorage()
    storage.init_db()

    # Load dataset
    raw_tasks = load_golden_dataset(dataset_path)

    # Insert tasks
    inserted = 0
    skipped = 0
    for task_dict in raw_tasks:
        task = EvalTask.from_dict(task_dict)
        try:
            storage.save_task(task)
            inserted += 1
        except Exception as e:
            print(f"  ⚠ Skipped task '{task.name}' (id={task.id}): {e}")
            skipped += 1

    settings = get_settings()
    print(f"✓ Seeded {inserted} tasks into {settings.db_path}")
    if skipped:
        print(f"  ⚠ {skipped} tasks skipped due to errors")

    # Print summary
    all_tasks = storage.get_tasks()
    print(f"  Total tasks in database: {len(all_tasks)}")
    for t in all_tasks:
        tags_str = ", ".join(t.tags) if t.tags else "none"
        print(f"    • {t.id}: {t.name} [{tags_str}]")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Seed EvalOps database with golden dataset tasks")
    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="Path to the golden dataset JSON file (default: golden_datasets/example_dataset.json)"
    )
    args = parser.parse_args()

    seed_database(dataset_path=args.dataset)
