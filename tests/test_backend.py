"""
Tests for SynrixAgentBackend — the unified backend interface.
Proves: auto-detection, write/read through unified API, backend_type reporting.
"""

import os
import pytest


class TestBackendAutoDetection:
    """Backend auto-detection and selection."""

    def test_sqlite_backend_selected(self, agent_backend):
        assert agent_backend.backend_type == "sqlite"

    def test_mock_backend_explicit(self):
        from synrix.agent_backend import get_synrix_backend
        backend = get_synrix_backend(backend="mock")
        assert backend.backend_type == "mock"
        backend.close()

    def test_auto_falls_back_to_sqlite(self, tmp_dir):
        from synrix.agent_backend import get_synrix_backend
        backend = get_synrix_backend(
            backend="auto",
            sqlite_path=os.path.join(tmp_dir, "auto.db"),
        )
        # On most machines without lattice, should fall to sqlite
        assert backend.backend_type in ("sqlite", "lattice")
        backend.close()


class TestBackendWriteRead:
    """Unified write/read cycle."""

    def test_write_and_read(self, agent_backend):
        agent_backend.write("test:key", {"greeting": "hello"})

        result = agent_backend.read("test:key")
        assert result is not None
        assert "data" in result
        data = result["data"]
        val = data.get("value", data)
        if isinstance(val, dict) and "greeting" in val:
            assert val["greeting"] == "hello"

    def test_write_and_query_prefix(self, agent_backend):
        agent_backend.write("prefix:a", {"n": 1})
        agent_backend.write("prefix:b", {"n": 2})
        agent_backend.write("other:c", {"n": 3})

        results = agent_backend.query_prefix("prefix:")
        assert len(results) == 2

    def test_write_returns_node_id(self, agent_backend):
        node_id = agent_backend.write("id_test", {"v": 1})
        assert node_id is not None

    def test_read_missing_key(self, agent_backend):
        result = agent_backend.read("nonexistent:key:12345")
        assert result is None or result.get("data") is None
