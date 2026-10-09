"""
Celery task: process_issue

Full pipeline for a single GitHub issue:
  1. Collect repo context
  2. Open SandboxSession (clone + baseline)
  3. Run agent loop (Claude tool-use)
  4. Diff workspace → filter allowed files
  5. Create branch + commit files + open PR
  6. Poll CI, merge or comment failure
  7. Update task status in DB throughout
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

import asyncpg
import redis.asyncio as aioredis
import structlog

from src.celery_app import celery_app
from src.config import settings
from src.database import get_db_pool
from src.github_client.app_client import GitHubAppClient
from src.github_client.pr_manager import PRManager
from src.ingestion.repo_context import collect_repo_context
from src.sandbox.context import SandboxSession
from src.sandbox.differ import apply_diff_to_repo_files
from src.agent.loop import run_agent_loop

logger = structlog.get_logger()


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Helpers for DB status updates
# ---------------------------------------------------------------------------

async def _set_task_status(pool: asyncpg.Pool, task_id: str, status: str) -> None:
    await pool.execute(
        "UPDATE tasks SET status=$1, updated_at=$2 WHERE id=$3",
        status,
        _now(),
        uuid.UUID(task_id),
    )


async def _insert_agent_run(
    pool: asyncpg.Pool,
    task_id: str,
    iteration: int,
    prompt_tokens: int,
    completion_tokens: int,
    model: str,
    tool_calls: list,
    output_summary: str,
    started_at: datetime,
    finished_at: datetime,
) -> None:
    await pool.execute(
        """
        INSERT INTO agent_runs
            (id, task_id, iteration, prompt_tokens, completion_tokens,
             model, tool_calls, output_summary, started_at, finished_at)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
        """,
        uuid.uuid4(),
        uuid.UUID(task_id),
        iteration,
        prompt_tokens,
        completion_tokens,
        model,
        json.dumps(tool_calls),
        output_summary,
        started_at,
        finished_at,
    )


async def _insert_pull_request(
    pool: asyncpg.Pool,
    task_id: str,
    pr_number: int,
    branch_name: str,
) -> None:
    await pool.execute(
        """
        INSERT INTO pull_requests (id, task_id, pr_number, branch_name, ci_status)
        VALUES ($1,$2,$3,$4,$5)
        """,
        uuid.uuid4(),
        uuid.UUID(task_id),
        pr_number,
        branch_name,
        "pending",
    )


async def _update_pr_ci_status(
    pool: asyncpg.Pool, task_id: str, ci_status: str, merged_at: datetime | None = None
) -> None:
    await pool.execute(
        "UPDATE pull_requests SET ci_status=$1, merged_at=$2 WHERE task_id=$3",
        ci_status,
        merged_at,
        uuid.UUID(task_id),
    )


# ---------------------------------------------------------------------------
# Core async pipeline
# ---------------------------------------------------------------------------

async def _run_pipeline(task_id: str) -> None:
    log = logger.bind(task_id=task_id)
    pool = await get_db_pool()
    redis_client = aioredis.from_url(settings.redis_url)

    try:
        # ── 1. Fetch the task row ──────────────────────────────────────────
        row = await pool.fetchrow(
            "SELECT repo_full_name, issue_number, title, body, base_commit_sha "
            "FROM tasks WHERE id=$1",
            uuid.UUID(task_id),
        )
        if not row:
            log.error("task_not_found")
            return

        repo_full_name: str = row["repo_full_name"]
        issue_number: int = row["issue_number"]
        issue_title: str = row["title"]
        issue_body: str = row["body"] or ""
        base_commit_sha: str = row["base_commit_sha"] or ""

        log = log.bind(repo=repo_full_name, issue=issue_number)
        log.info("pipeline_start")

        await _set_task_status(pool, task_id, "running")

        # ── 2. Collect repo context ────────────────────────────────────────
        log.info("collecting_repo_context")
        repo_ctx = await collect_repo_context(
            repo_full_name=repo_full_name,
            base_branch="main",
        )

        # Use the SHA from the DB if the context fetch didn't override it
        if not base_commit_sha:
            base_commit_sha = repo_ctx.base_commit_sha

        repo_context_text = (
            f"### Directory Tree\n```\n{repo_ctx.tree}\n```\n\n"
            f"### README\n{repo_ctx.readme}\n\n"
            f"### Test Files\n{', '.join(repo_ctx.test_files) or 'none detected'}\n\n"
            f"### Dependencies\n{repo_ctx.dep_summary or 'none detected'}\n\n"
            f"### Language\n{repo_ctx.language}\n"
        )

        # ── 3. Open sandbox and run agent ─────────────────────────────────
        log.info("sandbox_session_start")
        run_start = _now()

        async with SandboxSession(
            task_id=task_id,
            repo_full_name=repo_full_name,
            base_commit_sha=base_commit_sha,
        ) as handle:
            log.info("agent_loop_start")
            summary = await run_agent_loop(
                task_id=task_id,
                container_id=handle.container_id,
                repo_context_text=repo_context_text,
                issue_title=issue_title,
                issue_body=issue_body,
                baseline=handle.baseline_results,
            )

            run_end = _now()

            # Persist per-iteration agent run records
            for rec in summary.iteration_records:
                await _insert_agent_run(
                    pool=pool,
                    task_id=task_id,
                    iteration=rec.iteration,
                    prompt_tokens=rec.prompt_tokens,
                    completion_tokens=rec.completion_tokens,
                    model=settings.primary_model,
                    tool_calls=rec.tool_calls,
                    output_summary=summary.output_text[:1000] if rec.iteration == summary.iterations else "",
                    started_at=run_start,
                    finished_at=run_end,
                )

            # Workspace diff is populated on context exit (after yield)
            # We do a manual snapshot here before the context closes so we can
            # get the diff inside the with-block.
            from src.sandbox.differ import snapshot_workspace, diff_workspaces

            snapshot_after = snapshot_workspace(handle.container_id)
            workspace_diff = diff_workspaces(handle.workspace_snapshot_before, snapshot_after)

        # After context exits, sandbox is destroyed. Now work with diff.
        log.info("agent_loop_complete", stop_reason=summary.stop_reason)

        # ── 4. Filter files ────────────────────────────────────────────────
        filtered = apply_diff_to_repo_files(
            diff=workspace_diff,
            allowed_extensions=settings.allowed_file_extensions,
            require_approval_patterns=settings.require_human_approval_for_patterns,
        )

        all_files_to_commit = {**filtered.clean_updates}

        if not all_files_to_commit:
            log.info("no_files_to_commit")
            await _set_task_status(pool, task_id, "no_changes")
            # Post comment on the issue
            pr_mgr = PRManager(redis_client=redis_client)
            await pr_mgr.post_comment(
                repo_full_name=repo_full_name,
                issue_number=issue_number,
                body=(
                    f"🤖 **AutoForge** ran {summary.iterations} iteration(s) but produced "
                    f"no committed file changes.\n\n"
                    f"**Agent summary:**\n{summary.output_text}"
                ),
            )
            return

        if filtered.flagged_updates:
            log.warning(
                "files_require_human_approval",
                files=list(filtered.flagged_updates.keys()),
            )
            pr_mgr = PRManager(redis_client=redis_client)
            await pr_mgr.post_comment(
                repo_full_name=repo_full_name,
                issue_number=issue_number,
                body=(
                    "⚠️ **AutoForge** produced changes in paths requiring human approval:\n"
                    + "\n".join(f"- `{p}`" for p in filtered.flagged_updates)
                    + "\n\nThese files will NOT be automatically committed."
                ),
            )

        # ── 5. Create branch + commit + open PR ───────────────────────────
        branch_name = f"autoforge/issue-{issue_number}-{task_id[:8]}"
        pr_mgr = PRManager(redis_client=redis_client)

        log.info("creating_branch", branch=branch_name)
        await pr_mgr.create_branch(repo_full_name, branch_name, base_commit_sha)

        log.info("committing_files", count=len(all_files_to_commit))
        await pr_mgr.commit_files(
            repo_full_name=repo_full_name,
            branch_name=branch_name,
            files=all_files_to_commit,
            message=f"fix: resolve issue #{issue_number} via AutoForge\n\n{summary.output_text[:500]}",
        )

        pr_body = (
            f"Closes #{issue_number}\n\n"
            f"## AutoForge Summary\n\n{summary.output_text}\n\n"
            f"---\n*Generated by AutoForge in {summary.iterations} agent iteration(s). "
            f"Total tokens: {summary.total_prompt_tokens + summary.total_completion_tokens}.*"
        )
        pr_number = await pr_mgr.open_pr(
            repo_full_name=repo_full_name,
            branch_name=branch_name,
            title=f"[AutoForge] Fix #{issue_number}: {issue_title[:60]}",
            body=pr_body,
        )
        log.info("pr_opened", pr_number=pr_number)

        await _insert_pull_request(pool, task_id, pr_number, branch_name)
        await _set_task_status(pool, task_id, "pr_open")

        # ── 6. Poll CI and merge ───────────────────────────────────────────
        log.info("polling_ci", pr_number=pr_number)
        ci_result = await pr_mgr.poll_ci_status(repo_full_name, pr_number, timeout_seconds=600)
        await _update_pr_ci_status(pool, task_id, ci_result.status)

        if ci_result.status == "success":
            log.info("ci_passed_merging", pr_number=pr_number)
            merged = await pr_mgr.merge_pr(repo_full_name, pr_number)
            if merged:
                await _update_pr_ci_status(pool, task_id, "merged", merged_at=_now())
                await _set_task_status(pool, task_id, "merged")
                log.info("pr_merged", pr_number=pr_number)
            else:
                await _set_task_status(pool, task_id, "merge_failed")
        else:
            # CI failed or timed out — leave PR open, post comment
            log.warning("ci_failed_or_timeout", ci_status=ci_result.status, pr=pr_number)
            await _set_task_status(pool, task_id, "ci_failed")
            await pr_mgr.post_comment(
                repo_full_name=repo_full_name,
                issue_number=issue_number,
                body=(
                    f"❌ **AutoForge**: CI {ci_result.status} on PR #{pr_number}.\n"
                    f"Failed checks: {', '.join(ci_result.failed_checks) or 'none reported'}.\n"
                    "The PR has been left open for manual review."
                ),
            )

    except Exception as exc:
        log.error("pipeline_error", error=str(exc), exc_info=True)
        try:
            await _set_task_status(pool, task_id, "failed")
        except Exception:
            pass
        raise

    finally:
        await redis_client.aclose()


# ---------------------------------------------------------------------------
# Celery task entry point
# ---------------------------------------------------------------------------

@celery_app.task(
    name="src.agent.tasks.process_issue",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def process_issue(self, task_id: str) -> dict:
    """Celery entry point — runs the async pipeline synchronously via asyncio.run."""
    log = logger.bind(task_id=task_id, celery_id=self.request.id)
    log.info("celery_task_started")
    try:
        asyncio.run(_run_pipeline(task_id))
        log.info("celery_task_complete")
        return {"task_id": task_id, "status": "complete"}
    except Exception as exc:
        log.error("celery_task_failed", error=str(exc))
        raise self.retry(exc=exc)
