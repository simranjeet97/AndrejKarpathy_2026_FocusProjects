"""
issue_tool.py — GitHub issue tools registered on the ToolRegistry.

Three tools:
  get_issue_details        — fetch issue body + all comments + labels
  post_progress_comment    — post "🤖 AutoForge update: …" (rate-limited to 5/task)
  search_codebase_for_term — grep /workspace/repo, returns first 15 lines

Redis keys used:
  "issue_comments:{task_id}"  →  integer count of comments posted this task
"""
from __future__ import annotations

import asyncio
import json

import redis.asyncio as aioredis
import structlog

from src.config import settings
from src.github_client.app_client import GitHubAppClient
from src.sandbox.manager import SandboxManager
from src.agent.tools.registry import registry

logger = structlog.get_logger()

_ISSUE_BODY_MAX_CHARS = 4000
_SEARCH_MAX_LINES = 15
_MAX_COMMENTS_PER_TASK = 5
_REPO_ROOT = "/workspace/repo"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_redis() -> aioredis.Redis:
    return aioredis.from_url(settings.redis_url)


async def _get_github_client(repo_full_name: str) -> tuple[GitHubAppClient, aioredis.Redis]:
    redis_client = _make_redis()
    app_client = GitHubAppClient(redis_client=redis_client)
    return app_client, redis_client


# ---------------------------------------------------------------------------
# get_issue_details
# ---------------------------------------------------------------------------

@registry.register(
    name="get_issue_details",
    description=(
        "Fetch a GitHub issue's body, all comments, and labels. "
        "Returns a formatted string (truncated to 4 000 chars). "
        "Useful for understanding full context before starting work."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "repo_full_name": {
                "type": "string",
                "description": "Repository in 'owner/repo' format.",
            },
            "issue_number": {
                "type": "integer",
                "description": "GitHub issue number.",
            },
        },
        "required": ["repo_full_name", "issue_number"],
    },
)
async def get_issue_details(
    container_id: str,
    task_id: str,
    repo_full_name: str,
    issue_number: int,
) -> str:
    loop = asyncio.get_running_loop()
    app_client, redis_client = await _get_github_client(repo_full_name)
    try:
        gh = await app_client.get_installation_client(repo_full_name)

        def _fetch():
            repo = gh.get_repo(repo_full_name)
            issue = repo.get_issue(issue_number)
            labels = [lbl.name for lbl in issue.labels]
            comments = list(issue.get_comments())
            return issue, labels, comments

        issue, labels, comments = await loop.run_in_executor(None, _fetch)

        parts = [
            f"Issue #{issue_number}: {issue.title}",
            f"State: {issue.state}",
            f"Labels: {', '.join(labels) or 'none'}",
            f"Author: {issue.user.login}",
            f"Created: {issue.created_at.isoformat()}",
            "",
            "## Body",
            issue.body or "(no body)",
        ]

        if comments:
            parts.append(f"\n## Comments ({len(comments)})")
            for c in comments:
                parts.append(f"\n**{c.user.login}** ({c.created_at.isoformat()}):")
                parts.append(c.body or "")

        full_text = "\n".join(parts)
        if len(full_text) > _ISSUE_BODY_MAX_CHARS:
            full_text = full_text[:_ISSUE_BODY_MAX_CHARS] + "\n\n[... truncated]"

        logger.info("tool_get_issue_details", task_id=task_id, repo=repo_full_name, issue=issue_number)
        return full_text

    finally:
        await redis_client.aclose()


# ---------------------------------------------------------------------------
# post_progress_comment
# ---------------------------------------------------------------------------

@registry.register(
    name="post_progress_comment",
    description=(
        "Post a progress update comment on the GitHub issue. "
        "Limited to 5 comments per task to avoid noise. "
        "Prefix '🤖 AutoForge update:' is added automatically."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "repo_full_name": {
                "type": "string",
                "description": "Repository in 'owner/repo' format.",
            },
            "issue_number": {
                "type": "integer",
                "description": "GitHub issue number.",
            },
            "message": {
                "type": "string",
                "description": "Progress message to post.",
            },
        },
        "required": ["repo_full_name", "issue_number", "message"],
    },
)
async def post_progress_comment(
    container_id: str,
    task_id: str,
    repo_full_name: str,
    issue_number: int,
    message: str,
) -> str:
    loop = asyncio.get_running_loop()
    redis_client = _make_redis()
    comment_key = f"issue_comments:{task_id}"

    try:
        # Rate-limit check
        raw = await redis_client.get(comment_key)
        count = int(raw) if raw else 0
        if count >= _MAX_COMMENTS_PER_TASK:
            logger.warning("tool_post_comment_rate_limited", task_id=task_id, count=count)
            return "rate limit: max comments reached"

        app_client = GitHubAppClient(redis_client=redis_client)
        gh = await app_client.get_installation_client(repo_full_name)
        body = f"🤖 AutoForge update:\n\n{message}"

        def _post():
            repo = gh.get_repo(repo_full_name)
            issue = repo.get_issue(issue_number)
            issue.create_comment(body)

        await loop.run_in_executor(None, _post)

        # Increment counter (TTL 24h so it self-cleans)
        await redis_client.setex(comment_key, 86400, count + 1)

        logger.info(
            "tool_post_comment",
            task_id=task_id,
            repo=repo_full_name,
            issue=issue_number,
            comment_count=count + 1,
        )
        return "comment posted"

    finally:
        await redis_client.aclose()


# ---------------------------------------------------------------------------
# search_codebase_for_term
# ---------------------------------------------------------------------------

@registry.register(
    name="search_codebase_for_term",
    description=(
        "Search the repository for a literal term using grep. "
        "Returns up to 15 matching lines in 'file:line:content' format. "
        "Use this to locate existing code before patching."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "term": {
                "type": "string",
                "description": "Literal string to search for.",
            },
        },
        "required": ["term"],
    },
)
async def search_codebase_for_term(
    container_id: str,
    task_id: str,
    term: str,
) -> str:
    manager = SandboxManager()

    shell_cmd = (
        f"grep -rn --include='*.py' --include='*.md' --include='*.txt' "
        f"--include='*.json' --include='*.yaml' --include='*.toml' "
        f"-F -- {json.dumps(term)} {_REPO_ROOT} 2>/dev/null | head -n {_SEARCH_MAX_LINES}"
    )

    result = await manager.exec_in_sandbox(
        container_id=container_id,
        command=["sh", "-c", shell_cmd],
        timeout_seconds=15,
    )

    output = result.stdout.strip()
    if not output:
        return f"No matches found for: {term!r}"

    # Strip container-absolute path prefix for readability
    lines = []
    for line in output.splitlines():
        if line.startswith(_REPO_ROOT + "/"):
            line = line[len(_REPO_ROOT) + 1:]
        lines.append(line)

    logger.info("tool_search_codebase", task_id=task_id, term=term, matches=len(lines))
    return "\n".join(lines)
