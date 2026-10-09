"""
Unit tests for src/agent/tools/file_tools.py

Tests cover:
  - _safe_abs path validation (traversal rejection)
  - _check_extension_allowed enforcement
  - registry population (all 5 tools registered)
  - patch_file logic (not-found, multiple occurrences, happy path)

All SandboxManager I/O is mocked so no Docker daemon is required.
"""
from __future__ import annotations

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── Provide minimum env vars so pydantic-settings doesn't error ──────────────
@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy")
    monkeypatch.setenv("GITHUB_APP_ID", "1")
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY_PATH", ".")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "dummy")
    monkeypatch.setenv("DATABASE_URL", "postgresql://dummy")
    monkeypatch.setenv("REDIS_URL", "redis://localhost")
    monkeypatch.setenv("SANDBOX_IMAGE", "autoforge-sandbox:latest")


# Import AFTER env vars are patched
@pytest.fixture(autouse=True)
def _import_tools(_env):
    import importlib, src.agent.tools  # noqa: E401
    importlib.reload(src.agent.tools)


from src.agent.tools.file_tools import _safe_abs, _check_extension_allowed
from src.agent.tools.registry import registry

_REPO_ROOT = "/workspace/repo"


# ── _safe_abs ────────────────────────────────────────────────────────────────

class TestSafeAbs:
    def test_relative_path_resolved(self):
        assert _safe_abs("src/foo.py") == "/workspace/repo/src/foo.py"

    def test_dot_relative(self):
        assert _safe_abs(".") == "/workspace/repo"

    def test_already_absolute_inside_repo(self):
        assert _safe_abs("/workspace/repo/bar.py") == "/workspace/repo/bar.py"

    def test_traversal_with_dotdot_raises(self):
        with pytest.raises(PermissionError):
            _safe_abs("../../etc/passwd")

    def test_traversal_absolute_outside_raises(self):
        with pytest.raises(PermissionError):
            _safe_abs("/etc/shadow")

    def test_traversal_via_encoded_path_raises(self):
        with pytest.raises(PermissionError):
            _safe_abs("src/../../../tmp/evil")


# ── _check_extension_allowed ─────────────────────────────────────────────────

class TestExtensionAllowed:
    def test_py_allowed(self):
        _check_extension_allowed("/workspace/repo/foo.py")  # no exception

    def test_md_allowed(self):
        _check_extension_allowed("/workspace/repo/README.md")

    def test_sh_not_allowed(self):
        with pytest.raises(ValueError, match="Extension not allowed"):
            _check_extension_allowed("/workspace/repo/run.sh")

    def test_exe_not_allowed(self):
        with pytest.raises(ValueError):
            _check_extension_allowed("/workspace/repo/malware.exe")


# ── Registry population ───────────────────────────────────────────────────────

class TestRegistry:
    def test_all_five_tools_registered(self):
        names = {s["name"] for s in registry.schemas()}
        assert "read_file" in names
        assert "write_file" in names
        assert "patch_file" in names
        assert "list_directory" in names
        assert "search_in_files" in names

    def test_schemas_have_required_fields(self):
        for schema in registry.schemas():
            assert "name" in schema
            assert "description" in schema
            assert "input_schema" in schema


# ── patch_file logic ─────────────────────────────────────────────────────────

class TestPatchFileTool:
    """Tests the patch_file handler directly (mocking sandbox I/O)."""

    @pytest.mark.asyncio
    async def test_patch_not_found_raises(self):
        from src.agent.tools.file_tools import patch_file

        exec_result = MagicMock()
        exec_result.exit_code = 0  # file exists
        cat_result = MagicMock()
        cat_result.stdout = "def foo():\n    pass\n"

        with patch("src.agent.tools.file_tools.SandboxManager") as MockMgr:
            instance = MockMgr.return_value
            instance.exec_in_sandbox = AsyncMock(side_effect=[exec_result, cat_result])

            with pytest.raises(ValueError, match="not found"):
                await patch_file(
                    container_id="cid",
                    task_id="tid",
                    path="src/example.py",
                    old_str="MISSING_STRING",
                    new_str="replacement",
                )

    @pytest.mark.asyncio
    async def test_patch_multiple_occurrences_raises(self):
        from src.agent.tools.file_tools import patch_file

        exists_result = MagicMock()
        exists_result.exit_code = 0
        cat_result = MagicMock()
        cat_result.stdout = "foo\nfoo\n"

        with patch("src.agent.tools.file_tools.SandboxManager") as MockMgr:
            instance = MockMgr.return_value
            instance.exec_in_sandbox = AsyncMock(side_effect=[exists_result, cat_result])

            with pytest.raises(ValueError, match="appears 2 times"):
                await patch_file(
                    container_id="cid",
                    task_id="tid",
                    path="src/example.py",
                    old_str="foo",
                    new_str="bar",
                )

    @pytest.mark.asyncio
    async def test_patch_happy_path(self):
        from src.agent.tools.file_tools import patch_file

        original = "def add(a, b):\n    return a - b\n"
        expected_patched = "def add(a, b):\n    return a + b\n"

        exists_result = MagicMock()
        exists_result.exit_code = 0
        cat_result = MagicMock()
        cat_result.stdout = original
        mkdir_result = MagicMock()
        mkdir_result.exit_code = 0

        written_content: list[str] = []

        with patch("src.agent.tools.file_tools.SandboxManager") as MockMgr:
            instance = MockMgr.return_value
            instance.exec_in_sandbox = AsyncMock(
                side_effect=[exists_result, cat_result]
            )
            instance.write_file = MagicMock(
                side_effect=lambda cid, path, content: written_content.append(content)
            )

            result = await patch_file(
                container_id="cid",
                task_id="tid",
                path="src/math_utils.py",
                old_str="return a - b",
                new_str="return a + b",
            )

        assert "patched" in result
        assert len(written_content) == 1
        assert written_content[0] == expected_patched

    @pytest.mark.asyncio
    async def test_patch_file_not_found_raises(self):
        from src.agent.tools.file_tools import patch_file

        exists_result = MagicMock()
        exists_result.exit_code = 1  # file missing

        with patch("src.agent.tools.file_tools.SandboxManager") as MockMgr:
            instance = MockMgr.return_value
            instance.exec_in_sandbox = AsyncMock(return_value=exists_result)

            with pytest.raises(FileNotFoundError):
                await patch_file(
                    container_id="cid",
                    task_id="tid",
                    path="src/missing.py",
                    old_str="x",
                    new_str="y",
                )
