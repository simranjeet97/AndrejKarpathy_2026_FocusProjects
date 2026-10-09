"""
File-system tools for the AutoForge agent.

All tools are registered on the module-level `registry` singleton from
`src.agent.tools.registry`.  Import this module once (e.g. in
`src/agent/tools/__init__.py`) to populate the registry before building the
Anthropic API call.

Security guarantees
-------------------
* Paths are resolved against ``/workspace/repo`` — any ``..`` component that
  would escape that root raises ``PermissionError``.
* Write / patch operations are gated on ``ALLOWED_FILE_EXTENSIONS`` from
  ``settings``.  Read / list / search are unrestricted so the agent can
  explore the full repository.

All I/O is performed via ``SandboxManager.exec_in_sandbox`` (no direct host
filesystem access).
"""
from __future__ import annotations

import json
import posixpath
from typing import Optional

import structlog

from src.config import settings
from src.sandbox.manager import SandboxManager
from src.agent.tools.registry import registry

logger = structlog.get_logger()

_REPO_ROOT = "/workspace/repo"


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _safe_abs(rel_path: str) -> str:
    """
    Resolve *rel_path* relative to _REPO_ROOT.

    Raises PermissionError if the resolved path escapes _REPO_ROOT.
    Accepts both relative paths ("src/foo.py") and absolute paths that are
    already under _REPO_ROOT ("/workspace/repo/src/foo.py").
    """
    # If the caller passed an absolute path, normalise it directly.
    # Otherwise join it under _REPO_ROOT first.
    if posixpath.isabs(rel_path):
        candidate = posixpath.normpath(rel_path)
    else:
        candidate = posixpath.normpath(posixpath.join(_REPO_ROOT, rel_path))

    if not candidate.startswith(_REPO_ROOT):
        raise PermissionError(
            f"Path '{rel_path}' resolves outside /workspace/repo: '{candidate}'"
        )
    return candidate


def _check_extension_allowed(path: str) -> None:
    """Raise ValueError when the file extension is not in ALLOWED_FILE_EXTENSIONS."""
    allowed = settings.allowed_file_extensions
    if not any(path.endswith(ext) for ext in allowed):
        raise ValueError(
            f"Extension not allowed for '{path}'. "
            f"Permitted: {allowed}"
        )


# ---------------------------------------------------------------------------
# read_file
# ---------------------------------------------------------------------------

@registry.register(
    name="read_file",
    description=(
        "Read the full content of a file inside the repository. "
        "Provide a path relative to the repository root (e.g. 'src/foo.py') "
        "or an absolute path under /workspace/repo."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path, relative to repo root or absolute under /workspace/repo.",
            },
        },
        "required": ["path"],
    },
)
async def read_file(container_id: str, task_id: str, path: str) -> str:
    abs_path = _safe_abs(path)

    manager = SandboxManager()

    # Check existence first
    exists = await manager.exec_in_sandbox(
        container_id=container_id,
        command=["test", "-f", abs_path],
        timeout_seconds=5,
    )
    if exists.exit_code != 0:
        raise FileNotFoundError(f"File not found: {abs_path}")

    result = await manager.exec_in_sandbox(
        container_id=container_id,
        command=["cat", abs_path],
        timeout_seconds=10,
    )
    logger.info("tool_read_file", task_id=task_id, path=abs_path)
    return result.stdout


# ---------------------------------------------------------------------------
# write_file
# ---------------------------------------------------------------------------

@registry.register(
    name="write_file",
    description=(
        "Write (create or fully overwrite) a file inside the repository. "
        "The path must use an allowed extension. "
        "Returns a confirmation string."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path relative to repo root.",
            },
            "content": {
                "type": "string",
                "description": "Complete new file content.",
            },
        },
        "required": ["path", "content"],
    },
)
async def write_file(container_id: str, task_id: str, path: str, content: str) -> str:
    abs_path = _safe_abs(path)
    _check_extension_allowed(abs_path)

    manager = SandboxManager()

    # Ensure parent directory exists
    parent = posixpath.dirname(abs_path)
    await manager.exec_in_sandbox(
        container_id=container_id,
        command=["mkdir", "-p", parent],
        timeout_seconds=5,
    )

    manager.write_file(container_id, abs_path, content)

    byte_len = len(content.encode("utf-8"))
    msg = f"written {path} ({byte_len} bytes)"
    logger.info("tool_write_file", task_id=task_id, path=abs_path, bytes=byte_len)
    return msg


# ---------------------------------------------------------------------------
# patch_file
# ---------------------------------------------------------------------------

@registry.register(
    name="patch_file",
    description=(
        "Replace the *first* occurrence of old_str with new_str in a file. "
        "Raises an error if old_str is not found or appears more than once "
        "(use write_file for wholesale rewrites). "
        "The path must use an allowed extension."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path relative to repo root.",
            },
            "old_str": {
                "type": "string",
                "description": "Exact string to find (must appear exactly once).",
            },
            "new_str": {
                "type": "string",
                "description": "Replacement string.",
            },
        },
        "required": ["path", "old_str", "new_str"],
    },
)
async def patch_file(
    container_id: str,
    task_id: str,
    path: str,
    old_str: str,
    new_str: str,
) -> str:
    abs_path = _safe_abs(path)
    _check_extension_allowed(abs_path)

    # Read current content
    exists_result = await SandboxManager().exec_in_sandbox(
        container_id=container_id,
        command=["test", "-f", abs_path],
        timeout_seconds=5,
    )
    if exists_result.exit_code != 0:
        raise FileNotFoundError(f"File not found: {abs_path}")

    manager = SandboxManager()
    cat_result = await manager.exec_in_sandbox(
        container_id=container_id,
        command=["cat", abs_path],
        timeout_seconds=10,
    )
    original = cat_result.stdout

    count = original.count(old_str)
    if count == 0:
        raise ValueError(
            f"old_str not found in '{path}'. "
            "Check for whitespace or line-ending differences."
        )
    if count > 1:
        raise ValueError(
            f"old_str appears {count} times in '{path}'. "
            "Provide a more specific string or use write_file."
        )

    patched = original.replace(old_str, new_str, 1)
    manager.write_file(container_id, abs_path, patched)

    byte_len = len(patched.encode("utf-8"))
    msg = f"patched {path} ({byte_len} bytes after patch)"
    logger.info("tool_patch_file", task_id=task_id, path=abs_path, bytes=byte_len)
    return msg


# ---------------------------------------------------------------------------
# list_directory
# ---------------------------------------------------------------------------

@registry.register(
    name="list_directory",
    description=(
        "List files and directories recursively under a path in the repository. "
        "Defaults to the repository root. "
        "Returns a tree-style formatted string."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory path relative to repo root. Defaults to '.'.",
                "default": ".",
            },
        },
        "required": [],
    },
)
async def list_directory(
    container_id: str,
    task_id: str,
    path: str = ".",
) -> str:
    abs_path = _safe_abs(path)
    manager = SandboxManager()

    result = await manager.exec_in_sandbox(
        container_id=container_id,
        command=["find", abs_path, "-not", "-path", "*/.git/*", "-not", "-name", ".git"],
        timeout_seconds=15,
    )
    if result.exit_code != 0:
        return json.dumps({"error": result.stderr or "find failed"})

    lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]

    # Build a simple indented tree by stripping the abs_path prefix
    tree_lines: list[str] = []
    for line in sorted(lines):
        rel = line[len(abs_path):].lstrip("/") if line.startswith(abs_path) else line
        depth = rel.count("/")
        indent = "  " * depth
        name = posixpath.basename(rel) or rel
        tree_lines.append(f"{indent}{name}")

    logger.info("tool_list_directory", task_id=task_id, path=abs_path, entries=len(tree_lines))
    return "\n".join(tree_lines) if tree_lines else "(empty)"


# ---------------------------------------------------------------------------
# search_in_files
# ---------------------------------------------------------------------------

@registry.register(
    name="search_in_files",
    description=(
        "Search for a text pattern across repository files. "
        "Returns up to 20 matching lines with their file paths and line numbers. "
        "Uses grep extended-regex syntax."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Extended-regex search pattern (grep -E).",
            },
            "file_glob": {
                "type": "string",
                "description": "Glob pattern for files to search. Defaults to '**/*.py'.",
                "default": "**/*.py",
            },
        },
        "required": ["pattern"],
    },
)
async def search_in_files(
    container_id: str,
    task_id: str,
    pattern: str,
    file_glob: str = "**/*.py",
) -> str:
    manager = SandboxManager()

    # Convert glob to a find+grep pipeline run inside sh -c
    # We cap output at 20 matching lines via head
    shell_cmd = (
        f"grep -rEn --include='{file_glob.replace('**/', '')}' "
        f"-- {json.dumps(pattern)} {_REPO_ROOT} 2>/dev/null | head -n 20"
    )

    result = await manager.exec_in_sandbox(
        container_id=container_id,
        command=["sh", "-c", shell_cmd],
        timeout_seconds=15,
    )

    output = result.stdout.strip()
    if not output:
        return f"No matches found for pattern: {pattern}"

    # Strip the container-absolute prefix for readability
    lines = []
    for line in output.splitlines():
        if line.startswith(_REPO_ROOT):
            line = line[len(_REPO_ROOT):].lstrip("/")
        lines.append(line)

    logger.info("tool_search_in_files", task_id=task_id, pattern=pattern, matches=len(lines))
    return "\n".join(lines)
