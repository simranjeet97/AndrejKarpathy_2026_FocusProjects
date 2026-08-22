"""Unit tests for memory store and retrieval."""

import pytest
from agent_learning.memory.store import MemoryStore, MemoryEntry
from agent_learning.memory.retrieval import MemoryRetriever

def test_memory_store_add_retrieve():
    store = MemoryStore()
    entry = MemoryEntry(task_id="dm_01", failure_pattern="off by one loop boundary", diagnosis="index error")
    store.add(entry)
    
    retriever = MemoryRetriever(store)
    results = retriever.retrieve("loop boundary error", k=1)
    assert len(results) == 1
    assert results[0].id == entry.id
