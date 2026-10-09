from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, Optional
from dataclasses import dataclass, field
import redis.asyncio as aioredis
import structlog

from src.config import settings
from src.github_client.app_client import GitHubAppClient
from src.sandbox.manager import SandboxManager
from src.sandbox.cloner import clone_repo_into_sandbox, BaselineResult
from src.sandbox.differ import snapshot_workspace, diff_workspaces, WorkspaceDiff

logger = structlog.get_logger()


@dataclass
class SandboxHandle:
    container_id: str
    workspace_snapshot_before: Dict[str, str]
    baseline_results: BaselineResult
    diff: Optional[WorkspaceDiff] = None
    logs: str = ""


@asynccontextmanager
async def SandboxSession(
    task_id: str,
    repo_full_name: str,
    base_commit_sha: str
) -> AsyncGenerator[SandboxHandle, None]:
    manager = SandboxManager()
    redis_client = aioredis.from_url(settings.redis_url)
    container_id = None
    handle = None

    try:
        # 1. On enter: Create sandbox
        logger.info("sandbox_session_enter", task_id=task_id, repo=repo_full_name)
        container_id = manager.create_sandbox(task_id)

        # 2. Get GitHub token and clone repo into sandbox
        app_client = GitHubAppClient(redis_client=redis_client)
        github_token = await app_client.get_installation_token(repo_full_name)
        
        baseline_results = await clone_repo_into_sandbox(
            container_id=container_id,
            repo_full_name=repo_full_name,
            base_commit_sha=base_commit_sha,
            github_token=github_token
        )

        # 3. Snapshot workspace (before state)
        snapshot_before = snapshot_workspace(container_id)

        # 4. Yield SandboxHandle
        handle = SandboxHandle(
            container_id=container_id,
            workspace_snapshot_before=snapshot_before,
            baseline_results=baseline_results
        )
        yield handle

        # 5. On exit (success): Diff workspaces and capture logs
        snapshot_after = snapshot_workspace(container_id)
        handle.diff = diff_workspaces(snapshot_before, snapshot_after)
        
        # Capture logs
        container = manager.client.containers.get(container_id)
        handle.logs = container.logs().decode("utf-8", errors="replace")
        logger.info("sandbox_session_success", task_id=task_id, container_id=container_id)

    except Exception as e:
        logger.error("sandbox_session_exception", task_id=task_id, container_id=container_id, error=str(e))
        if container_id:
            try:
                container = manager.client.containers.get(container_id)
                logs = container.logs().decode("utf-8", errors="replace")
                if handle:
                    handle.logs = logs
            except Exception:
                pass
        raise e

    finally:
        # 6. Always in finally: destroy sandbox and close redis
        if container_id:
            try:
                manager.destroy_sandbox(container_id, capture_logs=False)
            except Exception as de:
                logger.warning("sandbox_cleanup_warning", container_id=container_id, error=str(de))
        await redis_client.aclose()
        logger.info("sandbox_session_exit_complete", task_id=task_id)
