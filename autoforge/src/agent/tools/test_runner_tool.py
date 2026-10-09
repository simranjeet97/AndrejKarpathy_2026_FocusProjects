"""
test_runner_tool.py — run_tests registered on the ToolRegistry.

Executes pytest inside the sandbox, parses the JSON report, and detects
regressions against the baseline established at clone time.

The tool returns a human-readable summary string (consumed by the LLM) and
also stores the structured TestRunResult on the handler's return value so the
harness can inspect it.  Because the LLM only sees strings, we JSON-encode
TestRunResult and return that string — the loop's dispatch() will forward it
as the tool_result content.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List, Optional, Set

import structlog

from src.sandbox.manager import SandboxManager
from src.agent.tools.registry import registry

logger = structlog.get_logger()

_REPORT_PATH = "/workspace/test_results.json"
_MAX_FAILURES_REPORTED = 5
_TRACEBACK_MAX_CHARS = 500


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TestFailure:
    test_id: str
    message: str
    traceback_snippet: str


@dataclass
class TestRunResult:
    passed: int
    failed: int
    errors: int
    duration_seconds: float
    failures: List[TestFailure] = field(default_factory=list)
    regression: bool = False

    def to_llm_string(self) -> str:
        """Format for the LLM tool result."""
        lines = [
            f"pytest result: {self.passed} passed, {self.failed} failed, "
            f"{self.errors} errors  ({self.duration_seconds:.1f}s)",
        ]
        if self.regression:
            lines.append("⚠️  REGRESSION DETECTED — a previously-passing test now fails.")
        if self.failures:
            lines.append(f"\nTop failures (showing {len(self.failures)} of up to {_MAX_FAILURES_REPORTED}):")
            for f in self.failures:
                lines.append(f"  ✗ {f.test_id}")
                if f.message:
                    lines.append(f"    {f.message}")
                if f.traceback_snippet:
                    lines.append(f"    {f.traceback_snippet}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

@registry.register(
    name="run_tests",
    description=(
        "Run the pytest test suite inside the sandbox. "
        "Returns a summary of passed/failed/error counts, failure details "
        "(up to 5), and whether any previously-passing test now fails (regression). "
        "Use this after every set of edits to confirm correctness."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "test_path": {
                "type": "string",
                "description": "Directory or file to test, relative to /workspace/repo. Defaults to 'tests/'.",
                "default": "tests/",
            },
            "specific_test": {
                "type": "string",
                "description": "If set, run only this test node id (e.g. 'tests/test_foo.py::test_bar'). Overrides test_path.",
            },
            "baseline_test_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of test IDs that passed in the baseline run. Used for regression detection.",
                "default": [],
            },
        },
        "required": [],
    },
)
async def run_tests(
    container_id: str,
    task_id: str,
    test_path: str = "tests/",
    specific_test: Optional[str] = None,
    baseline_test_ids: Optional[List[str]] = None,
) -> str:
    manager = SandboxManager()
    target = specific_test if specific_test else test_path

    cmd = [
        "pytest",
        target,
        "--json-report",
        f"--json-report-file={_REPORT_PATH}",
        "-q",
        "--tb=short",
        "--timeout=30",
    ]

    logger.info("tool_run_tests_start", task_id=task_id, target=target)

    exec_res = await manager.exec_in_sandbox(
        container_id=container_id,
        command=cmd,
        cwd="/workspace/repo",
        timeout_seconds=90,
    )

    # Parse JSON report
    try:
        raw = manager.read_file(container_id, _REPORT_PATH)
        report = json.loads(raw)
    except Exception as exc:
        # pytest crashed before writing the report
        logger.error("tool_run_tests_no_report", task_id=task_id, error=str(exc))
        fallback = TestRunResult(
            passed=0,
            failed=0,
            errors=1,
            duration_seconds=0.0,
            failures=[TestFailure(
                test_id="<collection error>",
                message=exec_res.stderr[:500] or exec_res.stdout[:500],
                traceback_snippet="",
            )],
            regression=False,
        )
        return fallback.to_llm_string()

    summary = report.get("summary", {})
    passed = summary.get("passed", 0)
    failed = summary.get("failed", 0)
    errors = summary.get("error", 0)
    duration = report.get("duration", 0.0)

    # Build baseline set for regression detection
    baseline_set: Set[str] = set(baseline_test_ids or [])

    failures: List[TestFailure] = []
    regression = False

    for test in report.get("tests", []):
        outcome = test.get("outcome", "")
        nodeid = test.get("nodeid", "")

        if outcome in ("failed", "error"):
            # Regression check
            if nodeid in baseline_set:
                regression = True

            if len(failures) < _MAX_FAILURES_REPORTED:
                call_info = test.get("call") or test.get("setup") or {}
                longrepr = call_info.get("longrepr", "")
                # Flatten longrepr (may be str or list)
                if isinstance(longrepr, list):
                    longrepr = "\n".join(str(s) for s in longrepr)
                longrepr = str(longrepr)

                # Split into message (first line) + traceback
                parts = longrepr.split("\n", 1)
                message = parts[0][:200]
                traceback_snippet = (parts[1][:_TRACEBACK_MAX_CHARS] if len(parts) > 1 else "")

                failures.append(TestFailure(
                    test_id=nodeid,
                    message=message,
                    traceback_snippet=traceback_snippet,
                ))

    result = TestRunResult(
        passed=passed,
        failed=failed,
        errors=errors,
        duration_seconds=duration,
        failures=failures,
        regression=regression,
    )

    logger.info(
        "tool_run_tests_complete",
        task_id=task_id,
        passed=passed,
        failed=failed,
        errors=errors,
        regression=regression,
    )

    return result.to_llm_string()
