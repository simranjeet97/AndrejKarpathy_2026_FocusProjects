"""
Core agent execution loop.

Drives a Claude tool-use conversation until:
  - Claude responds with end_turn (no more tool calls)
  - MAX_AGENT_ITERATIONS is reached
  - A hard error occurs

Returns an AgentRunSummary with all token usage and the final text output.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import anthropic
import structlog

from src.config import settings
from src.sandbox.cloner import BaselineResult
from src.agent.tools import registry  # populates all @registry.register handlers on import

logger = structlog.get_logger()

# System prompt injected before each run
_SYSTEM_PROMPT = """\
You are AutoForge, an autonomous software engineering agent.
You are given a GitHub issue and full context about the repository.
Your job is to:
1. Understand the issue and locate the relevant code.
2. Implement a minimal, correct fix or feature inside /workspace/repo.
3. Run the test suite (run_tests) after each change and iterate until all pre-existing tests pass.
4. When satisfied, stop calling tools — emit a brief summary of every change you made.

Rules:
- Only modify files inside /workspace/repo.
- Do NOT modify test files unless the issue explicitly asks you to.
- Keep changes minimal and focused.
- If the task seems unsafe or out-of-scope, explain why and stop.
"""


@dataclass
class IterationRecord:
    iteration: int
    prompt_tokens: int
    completion_tokens: int
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class AgentRunSummary:
    output_text: str
    total_prompt_tokens: int
    total_completion_tokens: int
    iterations: int
    iteration_records: List[IterationRecord] = field(default_factory=list)
    stop_reason: str = "end_turn"


async def run_agent_loop(
    task_id: str,
    container_id: str,
    repo_context_text: str,
    issue_title: str,
    issue_body: str,
    baseline: BaselineResult,
) -> AgentRunSummary:
    """
    Drive the Claude tool-use loop for a single task.

    Args:
        task_id: UUID of the autoforge task (for logging).
        container_id: Running sandbox container to exec into.
        repo_context_text: Pre-formatted context string (tree + readme + deps).
        issue_title: GitHub issue title.
        issue_body: GitHub issue body.
        baseline: Baseline test results from the initial clone.

    Returns:
        AgentRunSummary with all iteration records and the final output.
    """
    log = logger.bind(task_id=task_id)
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key.get_secret_value())

    baseline_summary = (
        f"Baseline tests: {baseline.passed} passed, "
        f"{baseline.failed} failed, {baseline.error} errors."
    )

    # Build the initial user message
    initial_user_content = (
        f"## Repository Context\n\n{repo_context_text}\n\n"
        f"## Issue\n**{issue_title}**\n\n{issue_body}\n\n"
        f"## {baseline_summary}\n\n"
        "Begin working on the issue. Use the provided tools to explore, edit, and test."
    )

    messages: List[Dict[str, Any]] = [
        {"role": "user", "content": initial_user_content},
    ]

    total_prompt_tokens = 0
    total_completion_tokens = 0
    iteration_records: List[IterationRecord] = []
    final_text = ""
    stop_reason = "max_iterations"

    for iteration in range(1, settings.max_agent_iterations + 1):
        log.info("agent_loop_iteration", iteration=iteration)

        response = await client.messages.create(
            model=settings.primary_model,
            max_tokens=8192,
            system=_SYSTEM_PROMPT,
            tools=registry.schemas(),  # type: ignore[arg-type]
            messages=messages,
        )

        prompt_tokens = response.usage.input_tokens
        completion_tokens = response.usage.output_tokens
        total_prompt_tokens += prompt_tokens
        total_completion_tokens += completion_tokens

        # Collect tool calls from this turn
        tool_call_records: List[Dict[str, Any]] = []
        tool_use_blocks = []
        text_blocks = []

        for block in response.content:
            if block.type == "tool_use":
                tool_use_blocks.append(block)
                tool_call_records.append({"tool": block.name, "input": block.input})
            elif block.type == "text":
                text_blocks.append(block.text)

        if text_blocks:
            final_text = "\n".join(text_blocks)

        iteration_records.append(
            IterationRecord(
                iteration=iteration,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                tool_calls=tool_call_records,
            )
        )

        log.info(
            "agent_loop_response",
            iteration=iteration,
            stop_reason=response.stop_reason,
            tool_calls=[r["tool"] for r in tool_call_records],
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

        # Append assistant message to conversation
        messages.append({"role": "assistant", "content": response.content})

        # If Claude is done (no tool calls), exit loop
        if response.stop_reason == "end_turn" or not tool_use_blocks:
            stop_reason = "end_turn"
            break

        # Dispatch all tool calls and collect results
        tool_results = []
        for tool_block in tool_use_blocks:
            log.info("agent_tool_call", tool=tool_block.name, task_id=task_id)
            result_content = await registry.dispatch(
                tool_name=tool_block.name,
                tool_input=tool_block.input,
                container_id=container_id,
                task_id=task_id,
            )
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tool_block.id,
                    "content": result_content,
                }
            )

        # Feed tool results back as a user turn
        messages.append({"role": "user", "content": tool_results})

    else:
        log.warning("agent_loop_max_iterations_reached", task_id=task_id, iterations=settings.max_agent_iterations)

    log.info(
        "agent_loop_complete",
        task_id=task_id,
        stop_reason=stop_reason,
        total_prompt_tokens=total_prompt_tokens,
        total_completion_tokens=total_completion_tokens,
        iterations=len(iteration_records),
    )

    return AgentRunSummary(
        output_text=final_text,
        total_prompt_tokens=total_prompt_tokens,
        total_completion_tokens=total_completion_tokens,
        iterations=len(iteration_records),
        iteration_records=iteration_records,
        stop_reason=stop_reason,
    )
