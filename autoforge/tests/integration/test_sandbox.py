import pytest
import docker
import os
from unittest.mock import patch, AsyncMock
from src.sandbox.context import SandboxSession
from src.sandbox.cloner import BaselineResult
from src.sandbox.manager import SandboxManager


@pytest.mark.asyncio
async def test_sandbox_session_integration():
    # Set dummy env vars for pydantic settings validation
    with patch.dict(os.environ, {
        "ANTHROPIC_API_KEY": "dummy",
        "GITHUB_APP_ID": "123",
        "GITHUB_APP_PRIVATE_KEY_PATH": ".",
        "GITHUB_WEBHOOK_SECRET": "dummy",
        "DATABASE_URL": "postgresql://dummy",
        "REDIS_URL": "redis://localhost:6379/0",
        "SANDBOX_IMAGE": "autoforge-sandbox:latest",
    }):
        # Mock github token retrieval and repository cloning
        with patch("src.github_client.app_client.GitHubAppClient.get_installation_token", new_callable=AsyncMock) as mock_token, \
             patch("src.sandbox.context.clone_repo_into_sandbox", new_callable=AsyncMock) as mock_clone:
            
            mock_token.return_value = "dummy-token"
            mock_clone.return_value = BaselineResult(passed=1, failed=0, error=0, test_ids=["test_dummy.py"])

            task_id = "test-task-123"
            container_id = None

            # Open SandboxSession
            async with SandboxSession(
                task_id=task_id,
                repo_full_name="owner/repo",
                base_commit_sha="abcdef12345"
            ) as handle:
                container_id = handle.container_id
                assert container_id is not None
                
                # Check that the container actually exists in Docker daemon
                docker_client = docker.from_env()
                container = docker_client.containers.get(container_id)
                assert container.status in ("running", "created")

                # Write a file inside the sandbox using manager
                manager = SandboxManager()
                # Relative path 'src/new_code.py'
                manager.write_file(container_id, "/workspace/src/new_code.py", "print('hello world')")

            # After context block exits:
            # 1. Check that the file appears in the diff
            assert handle.diff is not None
            assert "src/new_code.py" in handle.diff.added
            assert handle.diff.added["src/new_code.py"] == "print('hello world')"

            # 2. Confirm the container is gone
            docker_client = docker.from_env()
            with pytest.raises(docker.errors.NotFound):
                docker_client.containers.get(container_id)
