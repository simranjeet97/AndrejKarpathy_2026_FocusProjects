import pytest
from typing import Generator

@pytest.fixture
def mock_settings() -> Generator[None, None, None]:
    """
    Pytest fixture to mock configuration settings during test runs.
    """
    pass

@pytest.fixture
def temp_db() -> Generator[None, None, None]:
    """
    Pytest fixture to initialize an ephemeral SQLite database for isolated test execution.
    """
    pass
