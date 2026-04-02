"""
Tests for the Octopoda MCP Server tools.
Calls tool functions directly (no MCP transport needed).
"""

import os
import pytest


@pytest.fixture
def mcp_env(tmp_dir, monkeypatch):
    """Set up environment for MCP tool testing (local mode, no API key)."""
    monkeypatch.setenv("SYNRIX_BACKEND", "sqlite")
    monkeypatch.setenv("SYNRIX_DATA_DIR", tmp_dir)
    monkeypatch.delenv("OCTOPODA_API_KEY", raising=False)

    from synrix_runtime.core.daemon import RuntimeDaemon
    from synrix_runtime.monitoring.metrics import MetricsCollector
    RuntimeDaemon.reset_instance()
    MetricsCollector._instance = None

    # Reset the MCP server state to force local mode
    from synrix_runtime.api import mcp_server
    mcp_server._client = None
    mcp_server._local_mode = False
    mcp_server._agents.clear()
    mcp_server._runtimes.clear()

    yield

    mcp_server._client = None
    mcp_server._local_mode = False
    mcp_server._agents.clear()
    mcp_server._runtimes.clear()
    RuntimeDaemon.reset_instance()
    MetricsCollector._instance = None


class TestMCPRememberRecall:

    def test_remember_and_recall(self, mcp_env):
        from synrix_runtime.api.mcp_server import octopoda_remember, octopoda_recall

        result = octopoda_remember("test_agent", "greeting", '{"msg": "hello"}')
        assert result["success"] is True
        assert result["key"] == "greeting"
        assert result["agent_id"] == "test_agent"

        recall = octopoda_recall("test_agent", "greeting")
        assert recall["found"] is True
        assert recall["value"]["msg"] == "hello"

    def test_remember_plain_text(self, mcp_env):
        from synrix_runtime.api.mcp_server import octopoda_remember, octopoda_recall

        octopoda_remember("text_agent", "note", "just a string")
        recall = octopoda_recall("text_agent", "note")
        assert recall["found"] is True
        assert recall["value"] == "just a string"

    def test_recall_missing_key(self, mcp_env):
        from synrix_runtime.api.mcp_server import octopoda_recall

        recall = octopoda_recall("ghost_agent", "nonexistent")
        assert recall["found"] is False

    def test_remember_with_tags(self, mcp_env):
        from synrix_runtime.api.mcp_server import octopoda_remember

        result = octopoda_remember("tag_agent", "task", '{"status": "done"}', tags=["work", "done"])
        assert result["success"] is True


class TestMCPSearch:

    def test_search_by_prefix(self, mcp_env):
        from synrix_runtime.api.mcp_server import octopoda_remember, octopoda_search

        octopoda_remember("search_agent", "task:1", '{"name": "first"}')
        octopoda_remember("search_agent", "task:2", '{"name": "second"}')
        octopoda_remember("search_agent", "other:1", '{"name": "other"}')

        result = octopoda_search("search_agent", "task:")
        assert result["count"] == 2

    def test_search_empty_prefix(self, mcp_env):
        from synrix_runtime.api.mcp_server import octopoda_search

        result = octopoda_search("empty_agent", "nothing:")
        assert result["count"] == 0


class TestMCPSnapshot:

    def test_snapshot_and_restore(self, mcp_env):
        from synrix_runtime.api.mcp_server import (
            octopoda_remember, octopoda_recall, octopoda_snapshot, octopoda_restore,
        )

        octopoda_remember("snap_agent", "key1", '{"val": "before"}')
        snap = octopoda_snapshot("snap_agent", label="v1")
        assert snap["label"] == "v1"
        assert snap["keys_captured"] >= 1

        # Overwrite
        octopoda_remember("snap_agent", "key1", '{"val": "after"}')
        recall = octopoda_recall("snap_agent", "key1")
        assert recall["value"]["val"] == "after"

        # Restore
        restore = octopoda_restore("snap_agent", label="v1")
        assert restore["label"] == "v1"
        assert restore["keys_restored"] >= 1

        # Value should be back
        recall2 = octopoda_recall("snap_agent", "key1")
        assert recall2["value"]["val"] == "before"


class TestMCPSharedMemory:

    def test_share_and_read(self, mcp_env):
        from synrix_runtime.api.mcp_server import octopoda_share, octopoda_read_shared

        result = octopoda_share("writer", "signal", '{"ready": true}', space="team")
        assert result["success"] is True

        read = octopoda_read_shared("reader", "signal", space="team")
        assert read["found"] is True
        assert read["value"]["ready"] is True

    def test_read_shared_missing(self, mcp_env):
        from synrix_runtime.api.mcp_server import octopoda_read_shared

        read = octopoda_read_shared("lonely", "missing_key")
        assert read["found"] is False


class TestMCPAgentManagement:

    def test_list_agents(self, mcp_env):
        from synrix_runtime.api.mcp_server import octopoda_remember, octopoda_list_agents

        # Create an agent by using it
        octopoda_remember("listed_agent", "k", '"v"')
        result = octopoda_list_agents()
        assert result["count"] >= 1

    def test_agent_stats(self, mcp_env):
        from synrix_runtime.api.mcp_server import octopoda_remember, octopoda_recall, octopoda_agent_stats

        octopoda_remember("stats_agent", "k1", '"v1"')
        octopoda_recall("stats_agent", "k1")

        stats = octopoda_agent_stats("stats_agent")
        assert stats["agent_id"] == "stats_agent"
        assert stats["total_writes"] >= 1
        assert stats["total_reads"] >= 1
        assert stats["total_operations"] >= 2

    def test_log_decision(self, mcp_env):
        from synrix_runtime.api.mcp_server import octopoda_log_decision

        result = octopoda_log_decision(
            "decision_agent", "chose_plan_B", "lower risk",
            context='{"alternatives": ["plan_A", "plan_B"]}'
        )
        assert result["logged"] is True
        assert result["decision"] == "chose_plan_B"


class TestMCPRuntimeCache:

    def test_runtime_reuse(self, mcp_env):
        from synrix_runtime.api.mcp_server import _get_runtime, _runtimes

        rt1 = _get_runtime("cache_test")
        rt2 = _get_runtime("cache_test")
        assert rt1 is rt2
        assert len(_runtimes) == 1

    def test_parse_value_json(self):
        from synrix_runtime.api.mcp_server import _parse_value

        assert _parse_value('{"a": 1}') == {"a": 1}
        assert _parse_value('[1, 2]') == [1, 2]
        assert _parse_value('"hello"') == "hello"

    def test_parse_value_plain(self):
        from synrix_runtime.api.mcp_server import _parse_value

        result = _parse_value("not json")
        assert result == {"value": "not json"}
