"""Safe code execution for generated solutions.

Runs generated code in isolated temporary directories with:
- subprocess isolation
- enforced timeouts
- restricted filesystem scope
- stdout/stderr capture
- automatic cleanup

WARNING: This is experimental code execution. It uses subprocess
isolation but does NOT provide full sandboxing. See docs/limitations.md
for security considerations.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from agent_learning.environment.task import Task, TaskResult


class TaskRunner:
    """Executes generated code solutions in isolated temp directories.

    Each task execution gets its own temporary directory that is
    cleaned up after the run. Code is never executed in the
    repository root.
    """

    def __init__(
        self,
        timeout: int = 30,
        cleanup: bool = True,
    ) -> None:
        self.timeout = timeout
        self.cleanup = cleanup

    def run_solution(
        self,
        task: Task,
        solution_code: str,
        test_code: str,
        use_hidden_tests: bool = False,
    ) -> TaskResult:
        """Execute a solution against tests in an isolated directory.

        Args:
            task: The task being solved.
            solution_code: Generated Python code.
            test_code: Test code to run (visible or hidden).
            use_hidden_tests: If True, run hidden tests instead.

        Returns:
            TaskResult with pass/fail status and details.
        """
        start_time = time.monotonic()
        work_dir = None

        try:
            # Create isolated temp directory
            work_dir = Path(tempfile.mkdtemp(prefix=f"agent_task_{task.id}_"))

            # Write solution
            solution_file = work_dir / "solution.py"
            solution_file.write_text(solution_code)

            # Write tests
            tests = task.hidden_tests if use_hidden_tests else test_code
            test_file = work_dir / "test_solution.py"
            test_file.write_text(tests)

            # Also write starter code for reference (tests may import from it)
            if task.starter_code:
                starter_file = work_dir / "starter.py"
                starter_file.write_text(task.starter_code)

            # Run tests via pytest
            effective_timeout = min(self.timeout, task.timeout_seconds)
            result = self._run_pytest(work_dir, effective_timeout)

            elapsed = time.monotonic() - start_time

            return TaskResult(
                task_id=task.id,
                success=result["exit_code"] == 0,
                tests_passed=result["passed"],
                tests_failed=result["failed"],
                tests_total=result["total"],
                stdout=result["stdout"],
                stderr=result["stderr"],
                exit_code=result["exit_code"],
                elapsed_seconds=elapsed,
            )

        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - start_time
            return TaskResult(
                task_id=task.id,
                success=False,
                stdout="",
                stderr=f"Timeout after {self.timeout}s",
                exit_code=-1,
                elapsed_seconds=elapsed,
                error="timeout",
            )
        except Exception as e:
            elapsed = time.monotonic() - start_time
            return TaskResult(
                task_id=task.id,
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=-1,
                elapsed_seconds=elapsed,
                error=str(e),
            )
        finally:
            if self.cleanup and work_dir and work_dir.exists():
                shutil.rmtree(work_dir, ignore_errors=True)

    def _run_pytest(self, work_dir: Path, timeout: int) -> dict:
        """Run pytest in the work directory and parse results.

        Args:
            work_dir: Directory containing solution and test files.
            timeout: Maximum execution time in seconds.

        Returns:
            Dict with exit_code, stdout, stderr, passed, failed, total.
        """
        env = os.environ.copy()
        # Ensure the work dir is on the Python path
        env["PYTHONPATH"] = str(work_dir)

        import sys

        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "test_solution.py", "-v", "--tb=short", "--no-header"],
            cwd=str(work_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )

        # Parse pytest output for pass/fail counts
        passed, failed, total = self._parse_pytest_output(proc.stdout + proc.stderr)

        return {
            "exit_code": proc.returncode,
            "stdout": proc.stdout[-2000:] if len(proc.stdout) > 2000 else proc.stdout,
            "stderr": proc.stderr[-2000:] if len(proc.stderr) > 2000 else proc.stderr,
            "passed": passed,
            "failed": failed,
            "total": total,
        }

    @staticmethod
    def _parse_pytest_output(output: str) -> tuple[int, int, int]:
        """Parse pytest output to extract pass/fail counts.

        Args:
            output: Combined pytest stdout+stderr.

        Returns:
            Tuple of (passed, failed, total).
        """
        import re

        passed = 0
        failed = 0

        # Look for summary line like "3 passed, 1 failed"
        summary_match = re.search(
            r"(\d+)\s+passed", output
        )
        if summary_match:
            passed = int(summary_match.group(1))

        fail_match = re.search(
            r"(\d+)\s+failed", output
        )
        if fail_match:
            failed = int(fail_match.group(1))

        error_match = re.search(
            r"(\d+)\s+error", output
        )
        if error_match:
            failed += int(error_match.group(1))

        total = passed + failed
        return passed, failed, total


class CodeExtractor:
    """Extracts Python code from model responses.

    Models often wrap code in markdown code blocks. This extracts
    the actual Python code for execution.
    """

    @staticmethod
    def extract(response: str) -> str:
        """Extract Python code from a model response.

        Handles:
        - ```python ... ``` blocks
        - ``` ... ``` blocks
        - Raw code without blocks

        Args:
            response: Raw model response text.

        Returns:
            Extracted Python code.
        """
        import re

        # Try to find ```python ... ``` blocks
        python_blocks = re.findall(
            r"```python\s*\n(.*?)```", response, re.DOTALL
        )
        if python_blocks:
            return "\n\n".join(python_blocks)

        # Try to find ``` ... ``` blocks
        code_blocks = re.findall(
            r"```\s*\n(.*?)```", response, re.DOTALL
        )
        if code_blocks:
            return "\n\n".join(code_blocks)

        # Return raw response (might be plain code)
        return response.strip()
