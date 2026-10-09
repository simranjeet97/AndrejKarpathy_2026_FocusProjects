import fnmatch
from typing import Dict, List, Tuple
from dataclasses import dataclass, field

from src.sandbox.manager import SandboxManager

@dataclass
class WorkspaceDiff:
    added: Dict[str, str] = field(default_factory=dict)
    modified: Dict[str, str] = field(default_factory=dict)
    deleted: List[str] = field(default_factory=list)


@dataclass
class FilteredDiffResult:
    clean_updates: Dict[str, str] = field(default_factory=dict)
    clean_deletions: List[str] = field(default_factory=list)
    flagged_updates: Dict[str, str] = field(default_factory=dict)
    flagged_deletions: List[str] = field(default_factory=list)


def snapshot_workspace(container_id: str) -> Dict[str, str]:
    manager = SandboxManager()
    files = manager.list_files(container_id, directory="/workspace")
    
    snapshot = {}
    for filepath in files:
        # Strip "/workspace/" prefix to get the relative path
        rel_path = filepath
        if filepath.startswith("/workspace/"):
            rel_path = filepath[len("/workspace/"):]
        elif filepath.startswith("/workspace"):
            rel_path = filepath[len("/workspace"):]
            if rel_path.startswith("/"):
                rel_path = rel_path[1:]

        try:
            content = manager.read_file(container_id, filepath)
            snapshot[rel_path] = content
        except Exception:
            # File might have been deleted between list and read
            continue
            
    return snapshot


def diff_workspaces(before: Dict[str, str], after: Dict[str, str]) -> WorkspaceDiff:
    added = {}
    modified = {}
    deleted = []

    for path, content in after.items():
        if path not in before:
            added[path] = content
        elif before[path] != content:
            modified[path] = content

    for path in before:
        if path not in after:
            deleted.append(path)

    return WorkspaceDiff(added=added, modified=modified, deleted=deleted)


def apply_diff_to_repo_files(
    diff: WorkspaceDiff,
    allowed_extensions: List[str],
    require_approval_patterns: List[str]
) -> FilteredDiffResult:
    clean_updates = {}
    clean_deletions = []
    flagged_updates = {}
    flagged_deletions = []

    # Helper to check if file matches any approval pattern
    def _needs_approval(path: str) -> bool:
        return any(fnmatch.fnmatch(path, pat) for pat in require_approval_patterns)

    # Helper to check if file ends with allowed extension
    def _is_allowed(path: str) -> bool:
        return any(path.endswith(ext) for ext in allowed_extensions)

    # Process added/modified files
    all_updates = {**diff.added, **diff.modified}
    for path, content in all_updates.items():
        if not _is_allowed(path):
            continue
        
        if _needs_approval(path):
            flagged_updates[path] = content
        else:
            clean_updates[path] = content

    # Process deleted files
    for path in diff.deleted:
        if not _is_allowed(path):
            continue
            
        if _needs_approval(path):
            flagged_deletions.append(path)
        else:
            clean_deletions.append(path)

    return FilteredDiffResult(
        clean_updates=clean_updates,
        clean_deletions=clean_deletions,
        flagged_updates=flagged_updates,
        flagged_deletions=flagged_deletions
    )
