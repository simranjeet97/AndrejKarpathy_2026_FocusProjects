"""
Anthropic tool schemas and dispatch for the autoforge agent.

Each tool wraps a SandboxManager operation so Claude can call them
via the tool-use API.  All handlers are async and return a plain str
that becomes the tool_result content.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

import structlog

from src.sandbox.manager import SandboxManager

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Tool schemas (passed to Anthropic API as `tools=`)
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "name": "read_file",
        "description": (
            "Read the content of a file inside /workspace/repo. "
            "Use absolute paths starting with /workspace/repo/."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the file."},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": (
            "Write (create or overwrite) a file inside /workspace/repo. "
            "Provide the full new content."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the file."},
                "content": {"type": "string", "description": "Full file content to write."},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "run_command",
        "description": (
            "Execute a shell command inside /workspace/repo. "
            "Returns stdout, stderr, and exit code. "
            "Do NOT use for running tests — use run_tests instead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Command as a list of tokens, e.g. ['ruff', 'check', '.']",
                },
                "timeout_seconds": {
                    "type": "integer",
                    "default": 30,
                    "description": "Max seconds to wait for the command to finish.",
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "run_tests",
        "description": (
            "Run the full pytest suite under /workspace/repo and return a JSON "
            "summary of passed / failed / error counts plus the list of failed test IDs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "extra_args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Additional pytest arguments, e.g. ['-k', 'test_foo'].",
                    "default": [],
                },
                "timeout_seconds": {
                    "type": "integer",
                    "default": 120,
                    "description": "Max seconds to wait.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "list_directory",
        "description": "List files recursively under a directory in /workspace/repo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Absolute path. Defaults to /workspace/repo.",
                    "default": "/workspace/repo",
                },
            },
            "required": [],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------

async def dispatch_tool(
    tool_name: str,
    tool_input: Dict[str, Any],
    container_id: str,
    task_id: str,
) -> str:
    """Route a Claude tool-use request to the appropriate sandbox operation."""
    manager = SandboxManager()

    try:
        if tool_name == "read_file":
            return _tool_read_file(manager, container_id, tool_input["path"])

        elif tool_name == "write_file":
            return _tool_write_file(manager, container_id, tool_input["path"], tool_input["content"])

        elif tool_name == "run_command":
            return await _tool_run_command(
                manager,
                container_id,
                tool_input["command"],
                tool_input.get("timeout_seconds", 30),
            )

        elif tool_name == "run_tests":
            return await _tool_run_tests(
                manager,
                container_id,
                tool_input.get("extra_args", []),
                tool_input.get("timeout_seconds", 120),
            )

        elif tool_name == "list_directory":
            return _tool_list_directory(
                manager,
                container_id,
                tool_input.get("directory", "/workspace/repo"),
            )

        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

    except Exception as exc:
        logger.error("tool_dispatch_error", tool=tool_name, task_id=task_id, error=str(exc))
        return json.dumps({"error": str(exc)})


# ---------------------------------------------------------------------------
# Individual tool implementations
# ---------------------------------------------------------------------------

def _tool_read_file(manager: SandboxManager, container_id: str, path: str) -> str:
    content = manager.read_file(container_id, path)
    return content


def _tool_write_file(manager: SandboxManager, container_id: str, path: str, content: str) -> str:
    manager.write_file(container_id, path, content)
    return json.dumps({"ok": True, "path": path})


async def _tool_run_command(
    manager: SandboxManager,
    container_id: str,
    command: List[str],
    timeout_seconds: int,
) -> str:
    result = await manager.exec_in_sandbox(
        container_id=container_id,
        command=command,
        cwd="/workspace/repo",
        timeout_seconds=timeout_seconds,
    )
    return json.dumps(
        {
            "exit_code": result.exit_code,
            "stdout": result.stdout[-8000:],   # cap to avoid massive tool results
            "stderr": result.stderr[-4000:],
            "timed_out": result.timed_out,
        }
    )


async def _tool_run_tests(
    manager: SandboxManager,
    container_id: str,
    extra_args: List[str],
    timeout_seconds: int,
) -> str:
    report_path = "/workspace/agent_run_results.json"
    cmd = [
        "pytest",
        "--json-report",
        f"--json-report-file={report_path}",
        "-q",
        *extra_args,
    ]
    result = await manager.exec_in_sandbox(
        container_id=container_id,
        command=cmd,
        cwd="/workspace/repo",
        timeout_seconds=timeout_seconds,
    )
    try:
        raw = manager.read_file(container_id, report_path)
        report = json.loads(raw)
        summary = report.get("summary", {})
        failed_tests = [
            t["nodeid"]
            for t in report.get("tests", [])
            if t.get("outcome") in ("failed", "error")
        ]
        return json.dumps(
            {
                "passed": summary.get("passed", 0),
                "failed": summary.get("failed", 0),
                "error": summary.get("error", 0),
                "failed_test_ids": failed_tests,
                "exit_code": result.exit_code,
            }
        )
    except Exception:
        # Pytest might have crashed before writing the report
        return json.dumps(
            {
                "exit_code": result.exit_code,
                "stdout": result.stdout[-8000:],
                "stderr": result.stderr[-4000:],
                "timed_out": result.timed_out,
            }
        )


def _tool_list_directory(
    manager: SandboxManager, container_id: str, directory: str
) -> str:
    files = manager.list_files(container_id, directory=directory)
    return json.dumps({"files": files})
