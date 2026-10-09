import json
import structlog
from typing import List
from dataclasses import dataclass

from src.sandbox.manager import SandboxManager

logger = structlog.get_logger()


@dataclass
class BaselineResult:
    passed: int
    failed: int
    error: int
    test_ids: List[str]


async def clone_repo_into_sandbox(
    container_id: str,
    repo_full_name: str,
    base_commit_sha: str,
    github_token: str
) -> BaselineResult:
    manager = SandboxManager()

    # 1. Construct authenticated clone URL
    clone_url = f"https://x-access-token:{github_token}@github.com/{repo_full_name}.git"

    # 2. Clone the repository (depth=50)
    logger.info("sandbox_cloner_clone_start", container_id=container_id, repo=repo_full_name)
    clone_res = await manager.exec_in_sandbox(
        container_id=container_id,
        command=["git", "clone", "--depth=50", clone_url, "/workspace/repo"],
        timeout_seconds=120
    )
    if clone_res.exit_code != 0:
        raise RuntimeError(f"Failed to clone repository: {clone_res.stderr}")

    # 3. Checkout base commit SHA
    logger.info("sandbox_cloner_checkout_start", container_id=container_id, commit=base_commit_sha)
    checkout_res = await manager.exec_in_sandbox(
        container_id=container_id,
        command=["git", "checkout", base_commit_sha],
        cwd="/workspace/repo",
        timeout_seconds=30
    )
    if checkout_res.exit_code != 0:
        raise RuntimeError(f"Failed to checkout commit {base_commit_sha}: {checkout_res.stderr}")

    # 4. Install dependencies
    # Detect pyproject.toml vs requirements.txt
    # We can check file existence using 'test -f'
    has_pyproject = await manager.exec_in_sandbox(
        container_id=container_id,
        command=["test", "-f", "/workspace/repo/pyproject.toml"],
        timeout_seconds=10
    )
    has_requirements = await manager.exec_in_sandbox(
        container_id=container_id,
        command=["test", "-f", "/workspace/repo/requirements.txt"],
        timeout_seconds=10
    )

    if has_pyproject.exit_code == 0:
        logger.info("sandbox_cloner_install_deps", type="pyproject.toml")
        install_res = await manager.exec_in_sandbox(
            container_id=container_id,
            command=["pip", "install", "-e", ".", "--quiet"],
            cwd="/workspace/repo",
            timeout_seconds=300
        )
    elif has_requirements.exit_code == 0:
        logger.info("sandbox_cloner_install_deps", type="requirements.txt")
        install_res = await manager.exec_in_sandbox(
            container_id=container_id,
            command=["pip", "install", "-r", "requirements.txt", "--quiet"],
            cwd="/workspace/repo",
            timeout_seconds=300
        )
    else:
        logger.info("sandbox_cloner_no_deps_file_found")
        install_res = None

    if install_res and install_res.exit_code != 0:
        raise RuntimeError(f"Dependency installation failed: {install_res.stderr}")

    # 5. Run pytest once to establish baseline
    logger.info("sandbox_cloner_baseline_test_run")
    test_res = await manager.exec_in_sandbox(
        container_id=container_id,
        command=["pytest", "--json-report", "--json-report-file=/workspace/baseline_results.json", "-q"],
        cwd="/workspace/repo",
        timeout_seconds=180
    )
    
    # Even if pytest returns non-zero (due to failing tests), we still parse the json report
    # to understand which tests failed as part of the baseline.
    try:
        report_content = manager.read_file(container_id, "/workspace/baseline_results.json")
        report = json.loads(report_content)
        
        summary = report.get("summary", {})
        passed = summary.get("passed", 0)
        failed = summary.get("failed", 0)
        error = summary.get("error", 0)
        
        tests = report.get("tests", [])
        test_ids = [t["nodeid"] for t in tests if "nodeid" in t]
        
        result = BaselineResult(
            passed=passed,
            failed=failed,
            error=error,
            test_ids=test_ids
        )
        logger.info("sandbox_cloner_baseline_complete", passed=passed, failed=failed, error=error)
        return result
    except Exception as e:
        logger.error("sandbox_cloner_baseline_failed_to_parse", error=str(e), exit_code=test_res.exit_code)
        # If pytest failed completely (e.g. no tests found, syntax error preventing startup), we return a dummy/failed result
        return BaselineResult(
            passed=0,
            failed=0,
            error=1,
            test_ids=[]
        )
