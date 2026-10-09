import asyncio
import time
from typing import Dict, List, Optional
from dataclasses import dataclass
import redis.asyncio as aioredis
import structlog
from github.GithubException import GithubException

from src.config import settings
from src.github_client.app_client import GitHubAppClient

logger = structlog.get_logger()


@dataclass
class CIResult:
    status: str  # "success" | "failure" | "timeout"
    check_names: List[str]
    failed_checks: List[str]


class PRManager:
    def __init__(self, redis_client: aioredis.Redis) -> None:
        self.redis = redis_client
        self.app_client = GitHubAppClient(redis_client=redis_client)

    async def create_branch(self, repo_full_name: str, branch_name: str, base_sha: str) -> str:
        loop = asyncio.get_running_loop()
        repo = await self.app_client.get_repo(repo_full_name)

        def _create():
            ref = f"refs/heads/{branch_name}"
            repo.create_git_ref(ref=ref, sha=base_sha)
            return branch_name

        try:
            result = await loop.run_in_executor(None, _create)
            logger.info("pr_manager_action", action="create_branch", repo=repo_full_name, result="success")
            return result
        except Exception as e:
            logger.error("pr_manager_action", action="create_branch", repo=repo_full_name, result="failure", error=str(e))
            raise e

    async def commit_files(
        self, repo_full_name: str, branch_name: str, files: Dict[str, str], message: str
    ) -> str:
        loop = asyncio.get_running_loop()
        repo = await self.app_client.get_repo(repo_full_name)

        def _commit():
            last_commit_sha = None
            for path, content in files.items():
                try:
                    # Check if file exists to update it
                    contents = repo.get_contents(path, ref=branch_name)
                    res = repo.update_file(
                        path=path,
                        message=message,
                        content=content,
                        sha=contents.sha,
                        branch=branch_name
                    )
                    last_commit_sha = res["commit"].sha
                except GithubException as ge:
                    if ge.status == 404:
                        # File does not exist, create it
                        res = repo.create_file(
                            path=path,
                            message=message,
                            content=content,
                            branch=branch_name
                        )
                        last_commit_sha = res["commit"].sha
                    else:
                        raise ge
            return last_commit_sha

        try:
            commit_sha = await loop.run_in_executor(None, _commit)
            logger.info("pr_manager_action", action="commit_files", repo=repo_full_name, result="success", commit_sha=commit_sha)
            return commit_sha
        except Exception as e:
            logger.error("pr_manager_action", action="commit_files", repo=repo_full_name, result="failure", error=str(e))
            raise e

    async def open_pr(self, repo_full_name: str, branch_name: str, title: str, body: str) -> int:
        loop = asyncio.get_running_loop()
        repo = await self.app_client.get_repo(repo_full_name)

        def _open():
            pr = repo.create_pull(
                title=title,
                body=body,
                head=branch_name,
                base=repo.default_branch
            )
            return pr.number

        try:
            pr_number = await loop.run_in_executor(None, _open)
            logger.info("pr_manager_action", action="open_pr", repo=repo_full_name, pr_number=pr_number, result="success")
            return pr_number
        except Exception as e:
            logger.error("pr_manager_action", action="open_pr", repo=repo_full_name, result="failure", error=str(e))
            raise e

    async def poll_ci_status(
        self, repo_full_name: str, pr_number: int, timeout_seconds: int = 600
    ) -> CIResult:
        loop = asyncio.get_running_loop()
        repo = await self.app_client.get_repo(repo_full_name)

        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            def _check_ci():
                pr = repo.get_pull(pr_number)
                sha = pr.head.sha
                commit = repo.get_commit(sha)
                
                check_runs = list(commit.get_check_runs())
                statuses = list(commit.get_statuses())

                check_names = []
                failed_checks = []
                pending = False

                # Evaluate Check Runs
                for run in check_runs:
                    check_names.append(run.name)
                    if run.status != "completed":
                        pending = True
                    elif run.conclusion not in ("success", "neutral", "skipped"):
                        failed_checks.append(run.name)

                # Evaluate Commit Statuses (only latest status per context)
                latest_statuses = {}
                for status in statuses:
                    if status.context not in latest_statuses:
                        latest_statuses[status.context] = status
                
                for context, status in latest_statuses.items():
                    check_names.append(context)
                    if status.state == "pending":
                        pending = True
                    elif status.state in ("failure", "error"):
                        failed_checks.append(context)

                # If no runs or statuses exist at all, we consider it pending/waiting to start
                if not check_runs and not latest_statuses:
                    pending = True

                return pending, check_names, failed_checks

            pending, check_names, failed_checks = await loop.run_in_executor(None, _check_ci)

            if not pending:
                status = "failure" if failed_checks else "success"
                logger.info(
                    "pr_manager_action",
                    action="poll_ci_status",
                    repo=repo_full_name,
                    pr_number=pr_number,
                    result=status,
                    failed_checks=failed_checks
                )
                return CIResult(status=status, check_names=check_names, failed_checks=failed_checks)

            # Wait before next poll
            await asyncio.sleep(30)

        logger.warning(
            "pr_manager_action",
            action="poll_ci_status",
            repo=repo_full_name,
            pr_number=pr_number,
            result="timeout"
        )
        return CIResult(status="timeout", check_names=[], failed_checks=[])

    async def merge_pr(self, repo_full_name: str, pr_number: int, merge_method: str = "squash") -> bool:
        loop = asyncio.get_running_loop()
        repo = await self.app_client.get_repo(repo_full_name)

        def _merge():
            pr = repo.get_pull(pr_number)
            status = pr.merge(merge_method=merge_method)
            return status.merged

        try:
            merged = await loop.run_in_executor(None, _merge)
            logger.info("pr_manager_action", action="merge_pr", repo=repo_full_name, pr_number=pr_number, result="success" if merged else "failure")
            return merged
        except Exception as e:
            logger.error("pr_manager_action", action="merge_pr", repo=repo_full_name, pr_number=pr_number, result="failure", error=str(e))
            return False

    async def close_pr_and_delete_branch(self, repo_full_name: str, pr_number: int, branch_name: str) -> None:
        loop = asyncio.get_running_loop()
        repo = await self.app_client.get_repo(repo_full_name)

        def _close_and_delete():
            # Close PR
            pr = repo.get_pull(pr_number)
            if pr.state == "open":
                pr.edit(state="closed")
            
            # Delete branch
            try:
                ref = repo.get_git_ref(f"heads/{branch_name}")
                ref.delete()
            except GithubException as ge:
                if ge.status != 404:
                    raise ge

        try:
            await loop.run_in_executor(None, _close_and_delete)
            logger.info("pr_manager_action", action="close_pr_and_delete_branch", repo=repo_full_name, pr_number=pr_number, result="success")
        except Exception as e:
            logger.error("pr_manager_action", action="close_pr_and_delete_branch", repo=repo_full_name, pr_number=pr_number, result="failure", error=str(e))
            raise e

    async def post_comment(self, repo_full_name: str, issue_number: int, body: str) -> None:
        loop = asyncio.get_running_loop()
        repo = await self.app_client.get_repo(repo_full_name)

        def _comment():
            issue = repo.get_issue(issue_number)
            issue.create_comment(body)

        try:
            await loop.run_in_executor(None, _comment)
            logger.info("pr_manager_action", action="post_comment", repo=repo_full_name, result="success")
        except Exception as e:
            logger.error("pr_manager_action", action="post_comment", repo=repo_full_name, result="failure", error=str(e))
            raise e
