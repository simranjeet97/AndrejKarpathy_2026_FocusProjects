"""Structured logging configuration for experiment runs.

Every agent run produces structured JSON logs with fields for
reproducibility and analysis. No secrets or API keys are logged.
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class ExperimentLogEntry:
    """A single structured log entry for an experiment step."""

    experiment_id: str
    condition: str
    task_id: str
    task_family: str
    seed: int
    model: str
    prompt_version: str = "v1"
    attempt: int = 0
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    test_executions: int = 0
    test_passed: int = 0
    test_failed: int = 0
    success: bool = False
    reflection_output: str | None = None
    memory_written: list[str] = field(default_factory=list)
    memory_retrieved: list[str] = field(default_factory=list)
    workflow_modification: str | None = None
    elapsed_seconds: float = 0.0
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    phase: str = ""  # feedback, evaluation, retention, cross_family, regression
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}


class StructuredLogger:
    """JSON structured logger for experiment runs.

    Writes one JSON object per line to a log file, plus optional
    human-readable output to stderr.
    """

    def __init__(
        self,
        log_dir: Path,
        experiment_id: str,
        format: str = "json",
        level: str = "INFO",
    ) -> None:
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.experiment_id = experiment_id
        self.format = format

        # File handler for JSON logs
        self.log_file = self.log_dir / f"{experiment_id}.jsonl"
        self._file_handle = open(self.log_file, "a")

        # Standard Python logger for console output
        self.logger = logging.getLogger(f"agent_learning.{experiment_id}")
        self.logger.setLevel(getattr(logging, level.upper()))
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stderr)
            handler.setFormatter(
                logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
            )
            self.logger.addHandler(handler)

    def log_entry(self, entry: ExperimentLogEntry) -> None:
        """Write a structured log entry."""
        self._file_handle.write(json.dumps(entry.to_dict()) + "\n")
        self._file_handle.flush()

        # Also log a human-readable summary
        status = "✓" if entry.success else "✗"
        self.logger.info(
            f"{status} [{entry.condition}] {entry.task_id} "
            f"(calls={entry.model_calls}, tokens={entry.total_tokens}, "
            f"tests={entry.test_executions}, {entry.elapsed_seconds:.1f}s)"
        )

    def log_event(self, event: str, **kwargs: Any) -> None:
        """Log a general event."""
        record = {
            "experiment_id": self.experiment_id,
            "event": event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **kwargs,
        }
        self._file_handle.write(json.dumps(record) + "\n")
        self._file_handle.flush()
        self.logger.info(f"[EVENT] {event}: {kwargs}")

    def log_phase_start(self, phase: str, condition: str) -> None:
        """Log the start of an experimental phase."""
        self.log_event("phase_start", phase=phase, condition=condition)

    def log_phase_end(self, phase: str, condition: str, summary: dict[str, Any]) -> None:
        """Log the end of an experimental phase with summary."""
        self.log_event("phase_end", phase=phase, condition=condition, summary=summary)

    def close(self) -> None:
        """Close the log file."""
        self._file_handle.close()

    def __enter__(self) -> "StructuredLogger":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
