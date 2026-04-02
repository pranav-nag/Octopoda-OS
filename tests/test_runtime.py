"""
Tests for AgentRuntime — the developer-facing API.
"""

import time
import pytest


class TestAgentRuntime:
    """Core AgentRuntime lifecycle tests."""

    def test_remember_and_recall(self, agent_runtime):
        result = agent_runtime.remember("color", {"value": "blue"})
        assert result.success
        assert result.latency_us > 0

        recalled = agent_runtime.recall("color")
        assert recalled.found
        assert recalled.value == "blue"

    def test_recall_missing_key(self, agent_runtime):
        recalled = agent_runtime.recall("nonexistent_key")
        assert not recalled.found
        assert recalled.value is None

    def test_remember_overwrites(self, agent_runtime):
        agent_runtime.remember("item", {"v": 1})
        agent_runtime.remember("item", {"v": 2})
        recalled = agent_runtime.recall("item")
        assert recalled.found
        assert recalled.value.get("v") == 2

    def test_search(self, agent_runtime):
        agent_runtime.remember("prefs:theme", {"value": "dark"})
        agent_runtime.remember("prefs:lang", {"value": "en"})
        agent_runtime.remember("other", {"value": "x"})

        result = agent_runtime.search("prefs:")
        assert result.count == 2
        keys = [item["key"] for item in result.items]
        assert "prefs:theme" in keys
        assert "prefs:lang" in keys

    def test_snapshot_and_restore(self, agent_runtime):
        agent_runtime.remember("k1", {"value": "v1"})
        agent_runtime.remember("k2", {"value": "v2"})

        snap = agent_runtime.snapshot("test_snap")
        assert snap.keys_captured >= 2
        assert snap.label == "test_snap"

        # Clear and restore
        agent_runtime.remember("k1", {"value": "overwritten"})
        restored = agent_runtime.restore("test_snap")
        assert restored.label == "test_snap"
        assert restored.keys_restored >= 2

    def test_handoff_claim_complete(self, agent_runtime):
        handoff = agent_runtime.handoff("task_1", "other_agent", {"action": "summarize"})
        assert handoff.success
        assert handoff.task_id == "task_1"

        claimed = agent_runtime.claim_task("task_1")
        assert claimed.found
        assert claimed.payload.get("status") == "claimed"

        completed = agent_runtime.complete_task("task_1", {"summary": "done"})
        assert completed.task_id == "task_1"

    def test_shared_memory(self, agent_runtime):
        agent_runtime.share("project_status", {"phase": "alpha"})
        result = agent_runtime.read_shared("project_status")
        assert result.found
        assert result.value.get("phase") == "alpha"

    def test_log_decision(self, agent_runtime):
        # Should not raise
        agent_runtime.log_decision(
            "Use GPT-4",
            "Higher accuracy needed for medical domain",
            {"domain": "medical"},
        )

    def test_get_stats(self, agent_runtime):
        agent_runtime.remember("a", {"v": 1})
        agent_runtime.recall("a")

        stats = agent_runtime.get_stats()
        assert stats.agent_id == "test_agent"
        assert stats.total_writes >= 1
        assert stats.total_reads >= 1
        assert stats.uptime_seconds >= 0

    def test_context_manager(self, tmp_dir, monkeypatch):
        monkeypatch.setenv("SYNRIX_BACKEND", "sqlite")
        monkeypatch.setenv("SYNRIX_DATA_DIR", tmp_dir)

        from synrix_runtime.core.daemon import RuntimeDaemon
        RuntimeDaemon.reset_instance()

        from synrix_runtime.api.runtime import AgentRuntime
        with AgentRuntime("ctx_agent", agent_type="test") as rt:
            rt.remember("x", {"value": 1})
            recalled = rt.recall("x")
            assert recalled.found

        RuntimeDaemon.reset_instance()

    def test_shutdown_creates_snapshot(self, tmp_dir, monkeypatch):
        monkeypatch.setenv("SYNRIX_BACKEND", "sqlite")
        monkeypatch.setenv("SYNRIX_DATA_DIR", tmp_dir)

        from synrix_runtime.core.daemon import RuntimeDaemon
        RuntimeDaemon.reset_instance()

        from synrix_runtime.api.runtime import AgentRuntime
        rt = AgentRuntime("shutdown_test", agent_type="test")
        rt.remember("data", {"important": True})
        rt.shutdown()

        # Verify shutdown snapshot was written
        result = rt.backend.read("agents:shutdown_test:snapshots:shutdown_auto")
        assert result is not None

        RuntimeDaemon.reset_instance()

    def test_remember_with_tags(self, agent_runtime):
        result = agent_runtime.remember("tagged", {"v": 1}, tags=["important", "config"])
        assert result.success
        recalled = agent_runtime.recall("tagged")
        assert recalled.found
        assert recalled.value.get("_tags") == ["important", "config"]

    def test_search_empty_prefix(self, agent_runtime):
        agent_runtime.remember("a", {"v": 1})
        result = agent_runtime.search("")
        assert result.count >= 1

    def test_restore_latest_snapshot(self, agent_runtime):
        agent_runtime.remember("data", {"v": "original"})
        agent_runtime.snapshot("snap_1")
        time.sleep(0.05)
        agent_runtime.remember("data2", {"v": "second"})
        agent_runtime.snapshot("snap_2")

        restored = agent_runtime.restore()  # No label = latest
        assert restored.keys_restored >= 1
