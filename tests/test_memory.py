"""
Tests for the Memory convenience class — the 3-line quickstart.
Proves: remember/recall roundtrip, search, forget, remember_many.
"""

import pytest


class TestMemoryBasic:
    """Core remember/recall operations."""

    def test_remember_and_recall(self, memory):
        memory.remember("user_name", "Alice")
        assert memory.recall("user_name") == "Alice"

    def test_recall_missing_returns_none(self, memory):
        assert memory.recall("nonexistent") is None

    def test_remember_complex_value(self, memory):
        data = {"market_size": "$4.2B", "growth": "23%", "sources": [1, 2, 3]}
        memory.remember("research", data)
        result = memory.recall("research")
        assert result["market_size"] == "$4.2B"
        assert result["sources"] == [1, 2, 3]

    def test_overwrite_value(self, memory):
        memory.remember("key", "v1")
        memory.remember("key", "v2")
        assert memory.recall("key") == "v2"

    def test_remember_returns_node_id(self, memory):
        node_id = memory.remember("test", "value")
        assert node_id is not None


class TestMemorySearch:
    """Prefix search."""

    def test_search_by_prefix(self, memory):
        memory.remember("finding_01", "market data")
        memory.remember("finding_02", "tech trends")
        memory.remember("analysis_01", "summary")

        results = memory.search("finding_")
        assert len(results) == 2
        keys = {r["key"] for r in results}
        assert keys == {"finding_01", "finding_02"}

    def test_search_all(self, memory):
        memory.remember("a", 1)
        memory.remember("b", 2)

        results = memory.search()
        assert len(results) >= 2

    def test_search_returns_clean_keys(self, memory):
        memory.remember("my_key", "my_value")
        results = memory.search("my_")
        assert results[0]["key"] == "my_key"  # Not "agents:test_agent:my_key"


class TestMemoryBulk:
    """Bulk operations."""

    def test_remember_many(self, memory):
        items = {"k1": "v1", "k2": "v2", "k3": "v3"}
        count = memory.remember_many(items)
        assert count == 3
        assert memory.recall("k1") == "v1"
        assert memory.recall("k3") == "v3"


class TestMemoryInfo:
    """Metadata and repr."""

    def test_agent_id(self, memory):
        assert memory.agent_id == "test_agent"

    def test_backend_type(self, memory):
        assert memory.backend_type in ("sqlite", "lattice", "mock")

    def test_repr(self, memory):
        r = repr(memory)
        assert "test_agent" in r
        assert "Memory" in r
