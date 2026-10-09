import pytest
from src.sandbox.differ import (
    diff_workspaces,
    apply_diff_to_repo_files,
    WorkspaceDiff
)


def test_diff_workspaces():
    before = {
        "existing.py": "print('hello')",
        "deleted.py": "print('goodbye')",
    }
    after = {
        "existing.py": "print('hello updated')",
        "added.py": "print('new file')",
    }

    diff = diff_workspaces(before, after)

    assert diff.added == {"added.py": "print('new file')"}
    assert diff.modified == {"existing.py": "print('hello updated')"}
    assert diff.deleted == ["deleted.py"]


def test_apply_diff_to_repo_files_filtering():
    diff = WorkspaceDiff(
        added={
            "src/main.py": "print('ok')",
            "docs/readme.md": "# Readme",
            "db/migrations/001_init.py": "migration code",
            "secrets/api_key.txt": "secret",
        },
        modified={
            "src/utils.py": "def foo(): pass",
            "unsupported.exe": "binary",
        },
        deleted=[
            "src/legacy.py",
            "secrets/old_secret.txt",
        ]
    )

    allowed_exts = [".py", ".md"]
    approval_patterns = ["**/migrations/**", "**/secrets/**"]

    result = apply_diff_to_repo_files(diff, allowed_exts, approval_patterns)

    # Allowed & not flagged -> clean_updates
    assert "src/main.py" in result.clean_updates
    assert "docs/readme.md" in result.clean_updates
    assert "src/utils.py" in result.clean_updates
    
    # Excluded extensions (unsupported.exe) -> not present at all
    assert "unsupported.exe" not in result.clean_updates
    assert "unsupported.exe" not in result.flagged_updates

    # Flagged path -> flagged_updates
    assert "db/migrations/001_init.py" in result.flagged_updates
    assert "secrets/api_key.txt" not in result.clean_updates  # not allowed ext (.txt)

    # Deletions
    assert "src/legacy.py" in result.clean_deletions
    assert "secrets/old_secret.txt" not in result.clean_deletions
    assert "secrets/old_secret.txt" not in result.flagged_deletions  # .txt not allowed
