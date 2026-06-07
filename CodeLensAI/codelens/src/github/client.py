import re
import logging
from typing import List, Dict, Optional
from github import Github, GithubException
from ..models import PREvent, FileDiff, ReviewResponse

logger = logging.getLogger(__name__)

class GitHubClientError(Exception):
    """Custom exception raised by the GitHubClient."""
    pass


class GitHubClient:
    """GitHub API client wrapping PyGithub to retrieve and post PR information."""

    def __init__(self, token: str) -> None:
        """
        Initialize the GitHub client.

        Args:
            token: GitHub API personal access token.
        """
        self.github = Github(token)

    def get_pr(self, repo_full_name: str, pr_number: int) -> PREvent:
        """
        Retrieve a Pull Request event information.

        Args:
            repo_full_name: The full repository name (e.g. 'owner/repo').
            pr_number: The pull request number.

        Returns:
            A PREvent instance populated with PR details.
        """
        try:
            repo = self.github.get_repo(repo_full_name)
            pr = repo.get_pull(pr_number)
            
            # Extract jira ticket from title using regex
            jira_match = re.search(r'[A-Z]+-\d+', pr.title)
            jira_ticket_id = jira_match.group(0) if jira_match else None
            
            # Fetch changed files
            changed_files = self.get_pr_diff(repo_full_name, pr_number)
            
            return PREvent(
                pr_id=pr.number,
                repo=repo_full_name,
                commit_sha=pr.head.sha,
                title=pr.title,
                body=pr.body,
                author=pr.user.login,
                changed_files=changed_files,
                jira_ticket_id=jira_ticket_id,
                created_at=pr.created_at
            )
        except GithubException as e:
            raise GitHubClientError(f"Failed to get PR {pr_number} from {repo_full_name}: {e}") from e
        except Exception as e:
            raise GitHubClientError(f"Unexpected error getting PR {pr_number}: {e}") from e

    def get_pr_diff(self, repo_full_name: str, pr_number: int) -> List[FileDiff]:
        """
        Retrieve the list of files and their diffs changed in the PR.

        Args:
            repo_full_name: The full repository name (e.g. 'owner/repo').
            pr_number: The pull request number.

        Returns:
            A list of FileDiff instances for each changed file.
        """
        try:
            repo = self.github.get_repo(repo_full_name)
            pr = repo.get_pull(pr_number)
            
            # Fetch changed files. PaginatedList handles >100 files via pagination.
            files_paginated = pr.get_files()
            file_diffs = []
            for f in files_paginated:
                file_diffs.append(self._parse_file_diff(f))
            return file_diffs
        except GithubException as e:
            raise GitHubClientError(f"Failed to get diff for PR {pr_number} from {repo_full_name}: {e}") from e
        except Exception as e:
            raise GitHubClientError(f"Unexpected error getting PR diff: {e}") from e


    def get_file_history(self, repo_full_name: str, file_path: str, n: int = 5) -> List[Dict]:
        """
        Retrieve the history (commits metadata) for a specific file.

        Args:
            repo_full_name: The full repository name.
            file_path: Relative path of the file in the repository.
            n: Number of history items to retrieve.

        Returns:
            A list of dictionaries with commit metadata (sha, message, author, date).
        """
        try:
            repo = self.github.get_repo(repo_full_name)
            commits = repo.get_commits(path=file_path)
            history = []
            for commit in commits[:n]:
                author_name = commit.commit.author.name if commit.commit.author else None
                commit_date = commit.commit.author.date.isoformat() if commit.commit.author and commit.commit.author.date else None
                history.append({
                    "sha": commit.sha,
                    "message": commit.commit.message,
                    "author": author_name,
                    "date": commit_date
                })
            return history
        except GithubException as e:
            raise GitHubClientError(f"Failed to get file history for {file_path} in {repo_full_name}: {e}") from e
        except Exception as e:
            raise GitHubClientError(f"Unexpected error getting file history: {e}") from e

    def post_review(self, repo_full_name: str, pr_number: int, review: ReviewResponse) -> bool:
        """
        Submit a pull request review with overall summary and inline comments.

        Args:
            repo_full_name: The full repository name.
            pr_number: The pull request number.
            review: The review response model with comments and approval status.

        Returns:
            True if the review was posted successfully, False otherwise.
        """
        try:
            repo = self.github.get_repo(repo_full_name)
            pr = repo.get_pull(pr_number)
            
            # Map approval enum/string to GitHub review event string
            approval_str = str(review.approval).upper()
            if "APPROVE" in approval_str:
                event = "APPROVE"
            elif "REQUEST_CHANGES" in approval_str or "REQUEST" in approval_str:
                event = "REQUEST_CHANGES"
            else:
                event = "COMMENT"
                
            # Prepare review comments from the issues list
            draft_comments = []
            for issue in review.issues:
                if issue.file_path and issue.line_number is not None:
                    draft_comments.append({
                        "path": issue.file_path,
                        "line": issue.line_number,
                        "body": f"**[{issue.severity}]** {issue.message}\n\n*Suggestion:* {issue.suggestion}"
                    })
            
            # Post the review using PyGithub
            if draft_comments:
                pr.create_review(body=review.summary, event=event, comments=draft_comments)
            else:
                pr.create_review(body=review.summary, event=event)
                
            return True
        except GithubException as e:
            raise GitHubClientError(f"Failed to post review to PR {pr_number} in {repo_full_name}: {e}") from e
        except Exception as e:
            raise GitHubClientError(f"Unexpected error posting review: {e}") from e

    def post_inline_comment(self, repo_full_name: str, pr_number: int, path: str, line: int, body: str) -> bool:
        """
        Post a single inline comment on a specific line of a file in the PR.

        Args:
            repo_full_name: The full repository name.
            pr_number: The pull request number.
            path: Relative path of the file.
            line: Line number to comment on.
            body: The comment text.

        Returns:
            True if comment was posted successfully, False otherwise.
        """
        try:
            repo = self.github.get_repo(repo_full_name)
            pr = repo.get_pull(pr_number)
            
            # Single comments can be posted by creating a COMMENT event review with one comment
            pr.create_review(
                body=f"Inline comment on {path}",
                event="COMMENT",
                comments=[{"path": path, "line": line, "body": body}]
            )
            return True
        except GithubException as e:
            raise GitHubClientError(f"Failed to post inline comment to PR {pr_number}: {e}") from e
        except Exception as e:
            raise GitHubClientError(f"Unexpected error posting inline comment: {e}") from e

    def _parse_file_diff(self, github_file: any) -> FileDiff:
        """
        Helper method to parse a PyGithub file object into a FileDiff model.

        Args:
            github_file: A PyGithub File object.

        Returns:
            A FileDiff model instance.
        """
        return FileDiff(
            path=github_file.filename,
            status=github_file.status,
            additions=github_file.additions,
            deletions=github_file.deletions,
            patch=github_file.patch
        )

