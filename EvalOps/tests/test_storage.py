import os
import sqlite3
import pytest
from evalops.storage import SQLiteStorage
from evalops.models import EvalTask, EvalRun, Regression

def test_init_db_creates_tables(temp_db_path):
    storage = SQLiteStorage()
    storage.db_path = temp_db_path
    
    # Initialize DB
    storage.init_db()
    
    # Verify tables exist via raw sqlite connection query
    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    assert "tasks" in tables
    assert "eval_runs" in tables
    assert "regressions" in tables
    assert "human_feedback" in tables


def test_save_get_task_roundtrip(temp_db_path, sample_tasks):
    storage = SQLiteStorage()
    storage.db_path = temp_db_path
    storage.init_db()

    # Save tasks
    for task in sample_tasks:
        storage.save_task(task)

    # Retrieve all
    retrieved = storage.get_tasks()
    assert len(retrieved) == 3
    
    # Check details of first task
    retrieved_map = {t.id: t for t in retrieved}
    assert retrieved_map["task_1"].name == "Task One"
    assert retrieved_map["task_1"].input_prompt == "Translate: hello"
    assert retrieved_map["task_1"].expected_output == "hola"
    assert "translation" in retrieved_map["task_1"].tags

    # Test filtering by tags
    filtered = storage.get_tasks(tags=["counting"])
    assert len(filtered) == 1
    assert filtered[0].id == "task_2"


def test_save_get_run_roundtrip(temp_db_path, sample_runs):
    storage = SQLiteStorage()
    storage.db_path = temp_db_path
    storage.init_db()

    # Save runs
    for run in sample_runs:
        storage.save_run(run)

    # Retrieve all
    retrieved = storage.get_runs()
    assert len(retrieved) == 3

    # Retrieve filtered
    filtered = storage.get_runs(run_id="batch_1", task_id="task_1")
    assert len(filtered) == 1
    assert filtered[0].output == "hola"
    assert filtered[0].score == 1.0


def test_get_baseline(temp_db_path):
    storage = SQLiteStorage()
    storage.db_path = temp_db_path
    storage.init_db()
    
    # Threshold in config is 0.7. Let's write two runs:
    # 1. Score = 0.5 (failing, shouldn't be baseline)
    # 2. Score = 0.8 (passing, newer)
    # 3. Score = 0.9 (passing, newest)
    
    run_fail = EvalRun(id="run_f", task_id="task_x", model="m", output="a", score=0.5, run_at="2026-06-27T00:00:00")
    run_pass1 = EvalRun(id="run_p1", task_id="task_x", model="m", output="b", score=0.8, run_at="2026-06-27T01:00:00")
    run_pass2 = EvalRun(id="run_p2", task_id="task_x", model="m", output="c", score=0.9, run_at="2026-06-27T02:00:00")

    storage.save_run(run_fail)
    storage.save_run(run_pass1)
    storage.save_run(run_pass2)

    # Should fetch the newest passing run (run_pass2 with score 0.9)
    baseline = storage.get_baseline("task_x")
    assert baseline is not None
    assert baseline.id == "run_p2"
    assert baseline.score == 0.9


def test_save_get_regression(temp_db_path):
    storage = SQLiteStorage()
    storage.db_path = temp_db_path
    storage.init_db()

    r = Regression(
        id="reg_1",
        run_id="batch_x",
        task_id="task_1",
        baseline_score=0.9,
        current_score=0.5,
        delta=-0.4,
        is_regression=True
    )
    storage.save_regression(r)

    retrieved = storage.get_regressions(run_id="batch_x")
    assert len(retrieved) == 1
    assert retrieved[0].id == "reg_1"
    assert retrieved[0].is_regression is True
    assert retrieved[0].delta == -0.4
