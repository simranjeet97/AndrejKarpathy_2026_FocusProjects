"""Isolation module to prevent cross-condition state leaks or contamination."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path


class ExperimentIsolation:
    """Manages isolated workspace environments for each experimental condition."""

    def __init__(self, base_dir: Path | str) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create_condition_dir(self, condition: str, run_id: int) -> Path:
        cond_dir = self.base_dir / f"run_{run_id}" / condition
        cond_dir.mkdir(parents=True, exist_ok=True)
        return cond_dir

    def cleanup(self, path: Path) -> None:
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
