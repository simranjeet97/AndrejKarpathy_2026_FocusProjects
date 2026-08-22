"""Structured memory store for the Memory agent condition.

External memory persists across tasks as structured entries containing:
- failure_pattern
- diagnosis
- strategy
- constraint
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class MemoryEntry:
    """A single structured memory entry."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    task_id: str = ""
    task_family: str = ""
    failure_pattern: str = ""
    diagnosis: str = ""
    strategy: str = ""
    constraint: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryEntry:
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            task_id=data.get("task_id", ""),
            task_family=data.get("task_family", ""),
            failure_pattern=data.get("failure_pattern", ""),
            diagnosis=data.get("diagnosis", ""),
            strategy=data.get("strategy", ""),
            constraint=data.get("constraint", ""),
            timestamp=data.get("timestamp", ""),
        )

    def to_prompt_str(self) -> str:
        """Format entry for agent prompt inclusion."""
        parts = []
        if self.failure_pattern:
            parts.append(f"- Pattern: {self.failure_pattern}")
        if self.diagnosis:
            parts.append(f"- Diagnosis: {self.diagnosis}")
        if self.strategy:
            parts.append(f"- Strategy: {self.strategy}")
        if self.constraint:
            parts.append(f"- Constraint: {self.constraint}")
        return "\n".join(parts)


class MemoryStore:
    """JSON-backed persistent memory store."""

    def __init__(self, storage_file: Path | str | None = None) -> None:
        self.storage_file = Path(storage_file) if storage_file else None
        self.entries: list[MemoryEntry] = []
        if self.storage_file and self.storage_file.exists():
            self.load()

    def add(self, entry: MemoryEntry) -> None:
        """Add a memory entry and save if file configured."""
        self.entries.append(entry)
        if self.storage_file:
            self.save()

    def load(self) -> None:
        """Load entries from JSON file."""
        if not self.storage_file or not self.storage_file.exists():
            return
        with open(self.storage_file, "r") as f:
            data = json.load(f)
            self.entries = [MemoryEntry.from_dict(item) for item in data]

    def save(self) -> None:
        """Save entries to JSON file."""
        if not self.storage_file:
            return
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.storage_file, "w") as f:
            json.dump([e.to_dict() for e in self.entries], f, indent=2)

    def clear(self) -> None:
        """Clear all entries."""
        self.entries.clear()
        if self.storage_file and self.storage_file.exists():
            self.storage_file.unlink()
