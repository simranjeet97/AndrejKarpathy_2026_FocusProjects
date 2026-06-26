import os
import tempfile
import pytest
from typing import Generator, List

# Set mock mode for all tests
os.environ["MOCK_OLLAMA"] = "true"

from evalops.config import get_settings, Settings
from evalops.models import EvalTask, EvalRun

@pytest.fixture
def temp_db_path() -> Generator[str, None, None]:
    """Provides a path to a temporary SQLite database file, cleaning it up after."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass

@pytest.fixture(autouse=True)
def configure_test_settings(temp_db_path: str) -> Generator[Settings, None, None]:
    """Configures global settings to use the temporary database path."""
    from evalops.config import reset_settings
    reset_settings()
    settings = get_settings()
    settings.db_path = temp_db_path
    settings.judge_threshold = 0.7
    yield settings
    reset_settings()

@pytest.fixture
def sample_tasks() -> List[EvalTask]:
    """Returns a list of 3 sample EvalTask objects."""
    return [
        EvalTask(
            id="task_1",
            name="Task One",
            input_prompt="Translate: hello",
            expected_output="hola",
            tags=["translation", "easy"]
        ),
        EvalTask(
            id="task_2",
            name="Task Two",
            input_prompt="Count words in: apple banana",
            expected_output="2",
            tags=["counting"]
        ),
        EvalTask(
            id="task_3",
            name="Task Three",
            input_prompt="Capitalize: world",
            expected_output="WORLD",
            tags=["case"]
        )
    ]

@pytest.fixture
def sample_runs() -> List[EvalRun]:
    """Returns a list of 3 sample EvalRun objects."""
    return [
        EvalRun(
            id="run_1",
            task_id="task_1",
            model="test-model",
            output="hola",
            score=1.0,
            latency_ms=150.0,
            tokens_used=12,
            run_id="batch_1"
        ),
        EvalRun(
            id="run_2",
            task_id="task_2",
            model="test-model",
            output="3",
            score=0.0,
            latency_ms=200.0,
            tokens_used=15,
            run_id="batch_1"
        ),
        EvalRun(
            id="run_3",
            task_id="task_3",
            model="test-model",
            output="WORLD",
            score=1.0,
            latency_ms=100.0,
            tokens_used=10,
            run_id="batch_1"
        )
    ]
