"""
shell_tool.py — run_command registered on the ToolRegistry.

Executes an allowlisted shell command inside the sandbox.
Any command whose prefix does not match the allowlist is rejected immediately
without touching the sandbox — the agent receives an error string explaining
what IS permitted.

Explicit denials (rm, curl, wget, ssh, nc, chmod, sudo, pip install --index-url,
git push) are checked first so the rejection message is clear.
"""
from __future__ import annotations

import json
import shlex
from dataclasses import dataclass
from typing import List

import structlog

from src.sandbox.manager import SandboxManager
from src.agent.tools.registry import registry

logger = structlog.get_logger()

_OUTPUT_MAX_CHARS = 3000
_TIMEOUT_SECONDS = 60

# Commands that must never run regardless of prefix matching
_DENIED_PATTERNS: List[str] = [
    "rm ",
    "rm\t",
    "curl ",
    "wget ",
    "ssh ",
    "nc ",
    "ncat ",
    "chmod ",
    "sudo ",
    "pip install --index-url",
    "pip install --extra-index-url",
    "git push",
]

# Ordered allowlist — first prefix match wins
_ALLOWED_PREFIXES: List[str] = [
    "pip install",
    "pip list",
    "ruff check",
    "ruff format",
    "python -m pytest",
    "python -c",
    "python src/",
    "cat ",
    "ls ",
    "find ",
    "echo ",
    "git diff",
    "git log",
]


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class CommandResult:
    exit_code: int
    output: str
    truncated: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_denied(command: str) -> bool:
    stripped = command.strip()
    return any(stripped.startswith(d) or f" {d.strip()} " in f" {stripped} "
               for d in _DENIED_PATTERNS)


def _is_allowed(command: str) -> bool:
    stripped = command.strip()
    return any(stripped.startswith(prefix) for prefix in _ALLOWED_PREFIXES)


def _truncate(text: str) -> tuple[str, bool]:
    if len(text) <= _OUTPUT_MAX_CHARS:
        return text, False
    return text[:_OUTPUT_MAX_CHARS] + "\n[...truncated]", True


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

@registry.register(
    name="run_command",
    description=(
        "Run an allowlisted shell command inside the repository sandbox. "
        "Permitted prefixes: pip install, pip list, ruff check, ruff format, "
        "python -m pytest, python -c, python src/, cat, ls, find, echo, git diff, git log. "
        "Dangerous commands (rm, curl, wget, ssh, git push, sudo, chmod, …) are always rejected. "
        "Output is truncated to 3 000 characters."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The full shell command string to run (e.g. 'ruff check src/').",
            },
        },
        "required": ["command"],
    },
)
async def run_command(
    container_id: str,
    task_id: str,
    command: str,
) -> str:
    # 1. Deny-list check first (takes priority over allow-list)
    if _is_denied(command):
        logger.warning("tool_run_command_denied", task_id=task_id, command=command)
        result = CommandResult(
            exit_code=1,
            output=f"Command not permitted: {command}\nThis command is explicitly blocked for security reasons.",
            truncated=False,
        )
        return json.dumps({"exit_code": result.exit_code, "output": result.output, "truncated": False})

    # 2. Allow-list check
    if not _is_allowed(command):
        allowed_str = ", ".join(f'"{p.rstrip()}"' for p in _ALLOWED_PREFIXES)
        result = CommandResult(
            exit_code=1,
            output=f"Command not permitted: {command}\nAllowed prefixes: {allowed_str}",
            truncated=False,
        )
        logger.warning("tool_run_command_not_allowed", task_id=task_id, command=command)
        return json.dumps({"exit_code": result.exit_code, "output": result.output, "truncated": False})

    # 3. Parse and execute
    try:
        tokens = shlex.split(command)
    except ValueError as exc:
        return json.dumps({"exit_code": 1, "output": f"Command parse error: {exc}", "truncated": False})

    manager = SandboxManager()
    exec_res = await manager.exec_in_sandbox(
        container_id=container_id,
        command=tokens,
        cwd="/workspace/repo",
        timeout_seconds=_TIMEOUT_SECONDS,
    )

    raw_output = exec_res.stdout + (("\n" + exec_res.stderr) if exec_res.stderr else "")
    output, truncated = _truncate(raw_output)

    logger.info(
        "tool_run_command",
        task_id=task_id,
        command=command,
        exit_code=exec_res.exit_code,
        output_length=len(raw_output),
        truncated=truncated,
    )

    return json.dumps({
        "exit_code": exec_res.exit_code,
        "output": output,
        "truncated": truncated,
        "timed_out": exec_res.timed_out,
    })
