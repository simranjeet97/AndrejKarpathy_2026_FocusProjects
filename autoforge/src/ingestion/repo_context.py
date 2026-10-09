import asyncio
import re
from typing import List, Optional
from dataclasses import dataclass
import redis.asyncio as aioredis
import structlog
from github.GithubException import GithubException

from src.config import settings
from src.github_client.app_client import GitHubAppClient

logger = structlog.get_logger()


@dataclass
class RepoContext:
    tree: str
    readme: str
    test_files: List[str]
    dep_summary: str
    language: str
    base_commit_sha: str


def parse_pyproject_deps(content: str) -> List[str]:
    deps = []
    in_deps_section = False
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            # Check if entering dependencies section
            in_deps_section = "dependencies" in line.lower()
            continue
        if in_deps_section:
            match = re.match(r'^([a-zA-Z0-9_\-\[\]]+)\s*=', line)
            if match:
                dep_name = match.group(1).strip()
                if dep_name.lower() != "python":
                    deps.append(dep_name)
    return deps


def parse_requirements_deps(content: str) -> List[str]:
    deps = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-r"):
            continue
        # Split on separators to get the package name
        match = re.match(r'^([a-zA-Z0-9_\-\[\]]+)', line)
        if match:
            deps.append(match.group(1))
    return deps


async def collect_repo_context(
    repo_full_name: str,
    base_branch: str,
    max_chars: int = 12000
) -> RepoContext:
    loop = asyncio.get_running_loop()
    
    # 1. Instantiate the GitHub App Client using a temporary Redis client
    redis_client = aioredis.from_url(settings.redis_url)
    try:
        app_client = GitHubAppClient(redis_client=redis_client)
        repo = await app_client.get_repo(repo_full_name)
        
        # 2. Get base_commit_sha from base_branch
        def _get_branch_sha():
            try:
                return repo.get_branch(base_branch).commit.sha
            except GithubException:
                # Fallback to default branch if base_branch is not found
                return repo.get_branch(repo.default_branch).commit.sha

        base_commit_sha = await loop.run_in_executor(None, _get_branch_sha)

        # 3. Fetch directory tree and filter test files
        def _fetch_tree_and_tests():
            try:
                git_tree = repo.get_git_tree(base_commit_sha, recursive=True)
                tree_elements = git_tree.tree
            except GithubException:
                # Fallback if recursive tree fails
                tree_elements = []

            filtered_entries = []
            test_files_list = []

            for entry in tree_elements:
                path = entry.path
                # Check exclusions
                parts = path.split("/")
                if any(p in (".git", "node_modules", "__pycache__") for p in parts):
                    continue
                if path.endswith(".pyc"):
                    continue
                
                # Check depth
                if len(parts) <= 3:
                    filtered_entries.append(path)
                
                # Check test pattern matching
                filename = parts[-1]
                is_test = (
                    filename.startswith("test_") and filename.endswith(".py")
                ) or (
                    filename.endswith("_test.py")
                ) or (
                    "tests/" in path
                )
                if is_test:
                    test_files_list.append(path)

            # Limit tree entries to 150
            tree_entries = filtered_entries[:150]
            tree_str = "\n".join(tree_entries)

            return tree_str, test_files_list

        tree_str, test_files = await loop.run_in_executor(None, _fetch_tree_and_tests)

        # 4. Fetch README.md
        def _fetch_readme():
            try:
                readme_file = repo.get_readme()
                content = readme_file.decoded_content.decode("utf-8")
                return content[:3000]
            except Exception:
                return ""

        readme_content = await loop.run_in_executor(None, _fetch_readme)

        # 5. Fetch dependencies
        def _fetch_dependencies():
            # Try pyproject.toml first
            try:
                pyproject = repo.get_contents("pyproject.toml", ref=base_commit_sha)
                content = pyproject.decoded_content.decode("utf-8")
                deps = parse_pyproject_deps(content)
                return ", ".join(deps)
            except Exception:
                pass
            
            # Fallback to requirements.txt
            try:
                reqs = repo.get_contents("requirements.txt", ref=base_commit_sha)
                content = reqs.decoded_content.decode("utf-8")
                deps = parse_requirements_deps(content)
                return ", ".join(deps)
            except Exception:
                pass

            return ""

        dep_summary = await loop.run_in_executor(None, _fetch_dependencies)

        # 6. Detect language
        language = repo.language or "Unknown"

    finally:
        await redis_client.aclose()

    # 7. Cap total context length at max_chars, truncating tree first if needed
    # We calculate the fixed lengths of other parts
    test_files_str = ", ".join(test_files)
    fixed_overhead_len = len(readme_content) + len(test_files_str) + len(dep_summary) + len(language) + len(base_commit_sha) + 100
    
    if fixed_overhead_len + len(tree_str) > max_chars:
        # Truncate tree
        allowed_tree_len = max(0, max_chars - fixed_overhead_len)
        tree_str = tree_str[:allowed_tree_len] + "\n... [truncated]"

    return RepoContext(
        tree=tree_str,
        readme=readme_content,
        test_files=test_files,
        dep_summary=dep_summary,
        language=language,
        base_commit_sha=base_commit_sha
    )
