"""
meta_tools.py — agent self-governance tools registered on the ToolRegistry.

Three tools:
  submit_plan        — validate + store the agent's work plan before it starts editing.
  submit_for_review  — self-gate: agent asserts readiness; harness decides whether to proceed.
  request_human_review — pause the task and flag it for a human operator.

Task state is stored in Redis under simple string keys scoped to task_id:
  "plan:{task_id}"                  →  JSON-encoded plan
  "human_review_required:{task_id}" →  reason string
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import redis.asyncio as aioredis
import structlog

from src.config import settings
from src.agent.tools.registry import registry

logger = structlog.get_logger()

_MIN_CONFIDENCE = 0.7
_PLAN_TTL = 86400        # 24 h
_REVIEW_FLAG_TTL = 86400


def _make_redis() -> aioredis.Redis:
    return aioredis.from_url(settings.redis_url)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ReviewDecision:
    proceed: bool
    reason: str

    def to_json(self) -> str:
        return json.dumps({"proceed": self.proceed, "reason": self.reason})


# ---------------------------------------------------------------------------
# submit_plan
# ---------------------------------------------------------------------------

@registry.register(
    name="submit_plan",
    description=(
        "Before making any edits, submit your implementation plan. "
        "List the files you intend to change, the tests you plan to write or run, "
        "and any risks. The plan is validated against the allowed file-extension policy. "
        "You MUST call this before writing any code."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "approach": {
                "type": "string",
                "description": "Plain-English description of the implementation approach.",
            },
            "files_to_change": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Relative paths of files you plan to modify or create.",
            },
            "tests_to_write": {
                "type": "array",
                "items": {"type": "string"},
                "description": "New test file paths or test IDs you will add.",
            },
            "risks": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Potential risks or unknowns (e.g. API changes, performance).",
            },
        },
        "required": ["approach", "files_to_change"],
    },
)
async def submit_plan(
    container_id: str,
    task_id: str,
    approach: str,
    files_to_change: list,
    tests_to_write: list = None,
    risks: list = None,
) -> str:
    tests_to_write = tests_to_write or []
    risks = risks or []

    allowed = settings.allowed_file_extensions
    blocked = [
        f for f in files_to_change
        if not any(f.endswith(ext) for ext in allowed)
    ]
    if blocked:
        return (
            f"Plan rejected — the following files have disallowed extensions: "
            f"{blocked}. Permitted: {allowed}"
        )

    plan = {
        "approach": approach,
        "files_to_change": files_to_change,
        "tests_to_write": tests_to_write,
        "risks": risks,
        "task_id": task_id,
    }

    redis_client = _make_redis()
    try:
        await redis_client.setex(f"plan:{task_id}", _PLAN_TTL, json.dumps(plan))
    finally:
        await redis_client.aclose()

    logger.info(
        "tool_submit_plan",
        task_id=task_id,
        files=files_to_change,
        tests=tests_to_write,
        risks=risks,
    )
    return "plan accepted — proceed to implementation"


# ---------------------------------------------------------------------------
# submit_for_review
# ---------------------------------------------------------------------------

@registry.register(
    name="submit_for_review",
    description=(
        "Call this when you believe your implementation is complete. "
        "The harness will proceed only if: tests_passed=true, regressions=false, "
        "and confidence >= 0.7. If any condition fails you will receive a specific "
        "reason and must continue working."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Brief description of what you changed and why.",
            },
            "tests_passed": {
                "type": "boolean",
                "description": "True if the full test suite passed after your changes.",
            },
            "regressions": {
                "type": "boolean",
                "description": "True if any previously-passing test now fails.",
            },
            "confidence": {
                "type": "number",
                "description": "Your confidence that the implementation is correct (0.0 – 1.0).",
            },
        },
        "required": ["summary", "tests_passed", "regressions", "confidence"],
    },
)
async def submit_for_review(
    container_id: str,
    task_id: str,
    summary: str,
    tests_passed: bool,
    regressions: bool,
    confidence: float,
) -> str:
    reasons = []

    if not tests_passed:
        reasons.append("tests_passed is False — fix failing tests before submitting")
    if regressions:
        reasons.append("regressions detected — one or more previously-passing tests now fail")
    if confidence < _MIN_CONFIDENCE:
        reasons.append(
            f"confidence {confidence:.2f} is below the minimum threshold of {_MIN_CONFIDENCE}"
        )

    if reasons:
        decision = ReviewDecision(proceed=False, reason="; ".join(reasons))
        logger.info(
            "tool_submit_for_review_rejected",
            task_id=task_id,
            reasons=reasons,
        )
    else:
        decision = ReviewDecision(proceed=True, reason="all gates passed")
        logger.info(
            "tool_submit_for_review_approved",
            task_id=task_id,
            confidence=confidence,
            summary=summary[:200],
        )

    return decision.to_json()


# ---------------------------------------------------------------------------
# request_human_review
# ---------------------------------------------------------------------------

@registry.register(
    name="request_human_review",
    description=(
        "Flag this task for human review and pause autonomous work. "
        "Use when you encounter ambiguity, security concerns, or a situation "
        "you cannot resolve safely on your own. "
        "Returns immediately — the task will be paused by the harness."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "Clear explanation of why human review is needed.",
            },
        },
        "required": ["reason"],
    },
)
async def request_human_review(
    container_id: str,
    task_id: str,
    reason: str,
) -> str:
    redis_client = _make_redis()
    try:
        await redis_client.setex(
            f"human_review_required:{task_id}",
            _REVIEW_FLAG_TTL,
            reason,
        )
    finally:
        await redis_client.aclose()

    logger.warning(
        "tool_human_review_requested",
        task_id=task_id,
        reason=reason,
    )
    return "human review requested — task paused"
