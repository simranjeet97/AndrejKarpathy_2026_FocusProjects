import pytest
from evalops.models import EvalTask, EvalRun
from evalops.storage import SQLiteStorage
from evalops.regression_engine import RegressionEngine

def test_regression_detect_no_baseline(temp_db_path):
    storage = SQLiteStorage()
    storage.db_path = temp_db_path
    storage.init_db()

    engine = RegressionEngine(storage=storage)
    current_run = EvalRun(id="run_1", task_id="task_1", model="m", output="abc", score=0.9, run_id="batch_1")

    # Detect should return None since there is no baseline
    result = engine.detect("task_1", current_run)
    assert result is None

    # Verify baseline is None initially because the run is not yet saved
    assert storage.get_baseline("task_1") is None

    # Save the run (this is normally done by the runner/api)
    storage.save_run(current_run)

    # Verify run is saved and retrieved as baseline
    baseline = storage.get_baseline("task_1")
    assert baseline is not None
    assert baseline.id == "run_1"
    assert baseline.score == 0.9


def test_regression_detect_score_drop_above_threshold(temp_db_path):
    storage = SQLiteStorage()
    storage.db_path = temp_db_path
    storage.init_db()

    # Save baseline (score = 0.95)
    baseline_run = EvalRun(id="run_base", task_id="task_1", model="m", output="abc", score=0.95, run_at="2026-06-27T00:00:00")
    storage.save_run(baseline_run)

    engine = RegressionEngine(storage=storage)
    # Current score = 0.8 (drop = -0.15, threshold = 0.1 -> exceeds 0.1)
    current_run = EvalRun(id="run_curr", task_id="task_1", model="m", output="abc", score=0.8, run_id="batch_1")

    regression = engine.detect("task_1", current_run)
    assert regression is not None
    assert regression.is_regression is True
    assert abs(regression.delta - (-0.15)) < 1e-5
    assert regression.baseline_score == 0.95
    assert regression.current_score == 0.8


def test_regression_detect_score_drop_below_threshold(temp_db_path):
    storage = SQLiteStorage()
    storage.db_path = temp_db_path
    storage.init_db()

    # Save baseline (score = 0.9)
    baseline_run = EvalRun(id="run_base", task_id="task_1", model="m", output="abc", score=0.9, run_at="2026-06-27T00:00:00")
    storage.save_run(baseline_run)

    engine = RegressionEngine(storage=storage)
    # Current score = 0.85 (drop = -0.05, threshold = 0.1 -> does NOT exceed 0.1)
    current_run = EvalRun(id="run_curr", task_id="task_1", model="m", output="abc", score=0.85, run_id="batch_1")

    regression = engine.detect("task_1", current_run)
    assert regression is None


def test_generate_report_structure(temp_db_path):
    storage = SQLiteStorage()
    storage.db_path = temp_db_path
    storage.init_db()

    # Save runs in a batch
    run1 = EvalRun(id="run_1", task_id="task_1", model="m", output="a", score=0.9, run_id="batch_1")
    run2 = EvalRun(id="run_2", task_id="task_2", model="m", output="b", score=0.5, run_id="batch_1")
    storage.save_run(run1)
    storage.save_run(run2)

    engine = RegressionEngine(storage=storage)
    report = engine.generate_report("batch_1")
    
    assert report["run_id"] == "batch_1"
    assert report["total_tasks"] == 2
    # threshold is 0.7. run1 passes (0.9), run2 fails (0.5)
    assert report["passed"] == 1
    assert report["failed"] == 1
    assert "regressions" in report
    assert report["avg_score"] == 0.7
