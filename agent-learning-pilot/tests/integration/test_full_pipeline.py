"""Integration test running full mock pipeline."""

import pytest
from agent_learning.experiment.config import ExperimentConfig
from agent_learning.experiment.runner import ExperimentRunner

def test_full_pipeline_mock(tmp_path):
    # Create a tiny mock task suite to avoid running all 48 benchmark tasks in CI
    mock_tasks_dir = tmp_path / "mock_tasks"
    mock_tasks_dir.mkdir()
    
    import json
    for task_id, family in [("dm_01", "data_manipulation"), ("al_01", "algorithms")]:
        tdir = mock_tasks_dir / task_id
        tdir.mkdir()
        meta = {
            "id": task_id,
            "family": family,
            "difficulty": "easy",
            "specification": "spec",
            "timeout_seconds": 10
        }
        with open(tdir / "task.json", "w") as f:
            json.dump(meta, f)
        (tdir / "starter.py").write_text("def solve(data): return data")
        (tdir / "visible_tests.py").write_text("def test_basic(): assert True")
        (tdir / "hidden_tests.py").write_text("def test_hidden(): assert True")

    cfg = ExperimentConfig()
    cfg.model.provider = "mock"
    cfg.experiment.runs = 1
    cfg.experiment.conditions = ["baseline"]
    cfg.budget.max_model_calls = 1
    cfg.budget.max_test_runs = 1
    cfg.dataset.tasks_dir = str(mock_tasks_dir)
    cfg.output.results_dir = str(tmp_path / "results")
    cfg.output.raw_dir = str(tmp_path / "results" / "raw")
    cfg.output.logs_dir = str(tmp_path / "results" / "logs")
    
    runner = ExperimentRunner(cfg)
    runner.run()
    
    assert (tmp_path / "results" / "raw").exists()

