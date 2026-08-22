"""Deterministic memory retrieval based on keyword overlap and task family."""

from __future__ import annotations

import re
from typing import Sequence

from agent_learning.memory.store import MemoryEntry, MemoryStore


class MemoryRetriever:
    """Retrieves relevant memories deterministically."""

    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def retrieve(
        self,
        query: str,
        task_family: str | None = None,
        k: int = 3,
    ) -> list[MemoryEntry]:
        """Retrieve top-k relevant memories using keyword matching & family bonus.

        Args:
            query: Task specification or problem description.
            task_family: Task family identifier for bonus scoring.
            k: Maximum number of memories to return.

        Returns:
            List of up to k MemoryEntry objects sorted by relevance score.
        """
        if not self.store.entries:
            return []

        query_words = set(re.findall(r"\w+", query.lower()))
        scored_entries: list[tuple[float, str, MemoryEntry]] = []

        for entry in self.store.entries:
            text = f"{entry.failure_pattern} {entry.diagnosis} {entry.strategy} {entry.constraint}".lower()
            entry_words = set(re.findall(r"\w+", text))

            # Word overlap score
            overlap = len(query_words.intersection(entry_words))

            # Family match bonus
            family_bonus = 2.0 if task_family and entry.task_family == task_family else 0.0

            score = float(overlap) + family_bonus

            # Tie-breaking with entry id for determinism
            scored_entries.append((score, entry.id, entry))

        # Sort descending by score, ascending by entry.id
        scored_entries.sort(key=lambda item: (-item[0], item[1]))

        # Return top-k with non-zero relevance if possible (or top k overall)
        selected = [item[2] for item in scored_entries[:k]]
        return selected
