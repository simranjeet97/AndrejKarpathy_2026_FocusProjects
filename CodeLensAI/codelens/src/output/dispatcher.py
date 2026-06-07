import logging
from typing import List

from ..models import PREvent, ReviewResponse, Issue
from ..github.client import GitHubClient
from ..output.excel_logger import ExcelLogger

logger = logging.getLogger(__name__)


class ReviewDispatcher:
    """Orchestrates posting reviews to GitHub and logging to persistent Excel history."""

    def __init__(self, github_client: GitHubClient, excel_logger: ExcelLogger) -> None:
        """
        Initialize the ReviewDispatcher.

        Args:
            github_client: GitHub client instance for posting reviews.
            excel_logger: Excel logger instance for spreadsheet logging.
        """
        self.github_client = github_client
        self.excel_logger = excel_logger

    def dispatch(self, pr_event: PREvent, review: ReviewResponse) -> None:
        """
        Orchestrate dispatching: format summary comment, post a single consolidated
        review with inline comments, log to Excel, and log metrics.

        Args:
            pr_event: The Pull Request event.
            review: Final review response.
        """
        logger.info(f"Dispatching review for {pr_event.repo} PR #{pr_event.pr_id}")

        # Build inline comments for CRITICAL/HIGH issues (max 10 to avoid noise)
        inline_issues = self._select_inline_issues(review)

        # Post a single consolidated review to GitHub (summary + inline comments)
        try:
            summary_comment = self._format_summary_comment(review)
            consolidated_review = review.model_copy(update={
                "summary": summary_comment,
                "issues": inline_issues
            })
            self.github_client.post_review(pr_event.repo, pr_event.pr_id, consolidated_review)
            logger.info(
                f"Successfully posted consolidated review with {len(inline_issues)} "
                f"inline comments to GitHub."
            )
        except Exception as e:
            logger.error(f"GitHub dispatch failed: {e}", exc_info=True)

        # Log to Excel spreadsheet (always runs regardless of GitHub success)
        try:
            self.excel_logger.log_review(pr_event, review)
            logger.info("Successfully logged review to Excel spreadsheet.")
        except Exception as e:
            logger.error(f"Excel logging failed: {e}", exc_info=True)

        # Log metrics (total issues, approval, tokens)
        logger.info(
            f"Review Metrics | Repo: {pr_event.repo} | PR: #{pr_event.pr_id} | "
            f"Approval: {review.approval} | Issues: {len(review.issues)} | "
            f"Tokens: {review.tokens_used} | Latency: {review.latency_ms:.1f}ms"
        )

    def _select_inline_issues(self, review: ReviewResponse) -> List[Issue]:
        """
        Select issues eligible for inline GitHub comments.
        Only CRITICAL and HIGH severity issues with a line_number are included,
        capped at 10 to prevent notification spam.

        Args:
            review: Final review response.

        Returns:
            A filtered list of Issue instances for inline commenting.
        """
        selected = []
        for issue in review.issues:
            if len(selected) >= 10:
                break
            severity_upper = str(issue.severity).upper()
            if issue.line_number is not None and severity_upper in ["CRITICAL", "HIGH"]:
                selected.append(issue)
        return selected

    def _format_summary_comment(self, review: ReviewResponse) -> str:
        """
        Build a formatted Markdown summary comment for GitHub.

        Args:
            review: Final review response.

        Returns:
            A formatted Markdown string.
        """
        approval_emoji = {
            "APPROVE": "✅",
            "REQUEST_CHANGES": "❌",
            "COMMENT": "💬"
        }

        status_str = str(review.approval).upper()
        emoji = approval_emoji.get(status_str, "💬")

        # Severity counts
        crit_cnt = sum(1 for i in review.issues if str(i.severity).upper() == "CRITICAL")
        high_cnt = sum(1 for i in review.issues if str(i.severity).upper() == "HIGH")
        med_cnt = sum(1 for i in review.issues if str(i.severity).upper() == "MEDIUM")
        low_cnt = sum(1 for i in review.issues if str(i.severity).upper() == "LOW")

        comment = (
            f"## {emoji} CodeLens AI Review Feedback\n\n"
            f"**Approval Status:** {status_str} {emoji}\n"
            f"**Review Confidence:** {review.confidence * 100:.1f}%\n\n"
            f"### Summary\n{review.summary}\n\n"
            f"### Issue Count by Severity\n"
            f"| Severity | Count |\n"
            f"| :--- | :--- |\n"
            f"| 🔴 Critical | {crit_cnt} |\n"
            f"| 🟠 High | {high_cnt} |\n"
            f"| 🟡 Medium | {med_cnt} |\n"
            f"| 🟢 Low | {low_cnt} |\n"
            f"| **Total** | **{len(review.issues)}** |\n"
        )
        return comment

