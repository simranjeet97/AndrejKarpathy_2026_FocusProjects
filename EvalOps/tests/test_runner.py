import pytest
import os
import json
from evalops.models import EvalTask
from evalops.runner import EvalRunner
from evalops.storage import SQLiteStorage

def test_load_dataset_success(tmp_path) -> None:
    """
    Test that the EvalRunner successfully loads and parses a valid golden dataset JSON.
    """
    runner = EvalRunner()
    
    # Create a temp dataset file
    dataset_file = tmp_path / "test_dataset.json"
    data = [
        {"id": "t1", "name": "Task 1", "input_prompt": "hello", "expected_output": "hola", "tags": []}
    ]
    dataset_file.write_text(json.dumps(data))
    
    tasks = [EvalTask.from_dict(t) for t in data]
    assert len(tasks) == 1
    assert tasks[0].name == "Task 1"


@pytest.mark.asyncio
async def test_run_single_task(temp_db_path) -> None:
    """
    Test that a single evaluation task runs successfully and returns expected structure.
    """
    runner = EvalRunner()
    runner.storage.db_path = temp_db_path
    runner.storage.init_db()

    task = EvalTask(id="task_1", name="Task 1", input_prompt="hello", expected_output="hola")
    
    run = await runner.run_task(task, "llama3")
    assert run.task_id == "task_1"
    assert run.model == "llama3"
    # Under MOCK_OLLAMA=true, ollama_client returns a default completion
    assert "mock completion" in run.output.lower() or "hola" in run.output.lower()
    assert run.tokens_used > 0
    assert run.latency_ms >= 0


@pytest.mark.asyncio
async def test_run_entire_suite(temp_db_path, tmp_path) -> None:
    """
    Test that running an entire evaluation suite correctly iterates through all tasks and persists results.
    """
    runner = EvalRunner()
    runner.storage.db_path = temp_db_path
    runner.storage.init_db()

    # Create a temp dataset file
    dataset_file = tmp_path / "test_dataset.json"
    data = [
        {"id": "t1", "name": "Task 1", "input_prompt": "hello", "expected_output": "hola", "tags": ["tag1"]}
    ]
    dataset_file.write_text(json.dumps(data))

    runs = await runner.run_from_dataset(str(dataset_file), "llama3")
    assert len(runs) == 1
    assert runs[0].model == "llama3"
    
    # Check that task and run are persisted
    db_tasks = runner.storage.get_tasks()
    assert len(db_tasks) == 1
    assert db_tasks[0].id == "t1"

    db_runs = runner.storage.get_runs(run_id=runs[0].run_id)
    assert len(db_runs) == 1
    assert db_runs[0].output == runs[0].output
