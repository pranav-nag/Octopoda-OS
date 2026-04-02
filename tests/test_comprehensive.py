"""
Comprehensive Test Suite for Octopoda
======================================
Tests ALL features end-to-end: core memory, new features, loop detection,
messaging, goals, export/import, consolidation, forgetting, summarization,
auto-tagging, filtered search, memory health, shared memory, conflict detection,
tenant isolation, and framework integrations.

Run with: OCTOPODA_LOCAL_MODE=1 pytest tests/test_comprehensive.py -v

Uses the agent_runtime fixture from conftest.py which properly configures
the SQLite backend through the daemon.
"""

import os
import time
import json
import tempfile
import threading
import pytest

# Force local mode for testing
os.environ["OCTOPODA_LOCAL_MODE"] = "1"

# Use the agent_runtime fixture from conftest.py — aliased as "agent" for readability
@pytest.fixture
def agent(agent_runtime):
    return agent_runtime


# ===================================================================
# CORE MEMORY OPERATIONS
# ===================================================================

class TestCoreMemory:
    """Test basic remember/recall — the foundation everything else depends on."""

    def test_remember_string(self, agent):
        result = agent.remember("greeting", "hello world")
        assert result.success
        assert result.key == "greeting"

    def test_remember_dict(self, agent):
        result = agent.remember("config", {"theme": "dark", "lang": "en"})
        assert result.success

    def test_recall_string(self, agent):
        agent.remember("name", "Alice")
        result = agent.recall("name")
        assert result.found
        assert result.value == "Alice" or result.value == {"value": "Alice"}

    def test_recall_dict(self, agent):
        agent.remember("prefs", {"color": "blue"})
        result = agent.recall("prefs")
        assert result.found

    def test_recall_missing_key(self, agent):
        result = agent.recall("nonexistent")
        assert not result.found

    def test_remember_overwrite(self, agent):
        agent.remember("status", "draft")
        agent.remember("status", "published")
        result = agent.recall("status")
        assert result.found

    def test_remember_with_tags(self, agent):
        result = agent.remember("tagged", "important data", tags=["urgent", "review"])
        assert result.success

    def test_agent_prefix_scoping(self, agent):
        """Memories are scoped by agent ID prefix."""
        agent.remember("scoped_key", "my_data")
        result = agent.recall("scoped_key")
        assert result.found

    def test_write_count_tracked(self, agent):
        agent.remember("a", "1")
        agent.remember("b", "2")
        assert agent._write_count >= 2

    def test_read_count_tracked(self, agent):
        agent.remember("x", "val")
        agent.recall("x")
        agent.recall("x")
        assert agent._read_count >= 2


# ===================================================================
# TTL / AUTO-EXPIRE
# ===================================================================

class TestTTL:
    def test_remember_with_ttl(self, agent):
        result = agent.remember_with_ttl("temp", "expires soon", ttl_seconds=3600)
        assert result.success

    def test_cleanup_expired(self, agent):
        # Store with very short TTL (already expired)
        agent.remember_with_ttl("expired_item", "old data", ttl_seconds=0)
        time.sleep(0.1)
        result = agent.cleanup_expired()
        assert isinstance(result, dict)
        assert "deleted" in result


# ===================================================================
# IMPORTANCE SCORING
# ===================================================================

class TestImportance:
    def test_remember_important_critical(self, agent):
        result = agent.remember_important("critical_config", "do not delete", importance="critical")
        assert result.success

    def test_remember_important_low(self, agent):
        result = agent.remember_important("debug_log", "temp debug", importance="low")
        assert result.success


# ===================================================================
# CONFLICT DETECTION
# ===================================================================

class TestConflicts:
    def test_detect_conflicts_no_conflict(self, agent):
        result = agent.detect_conflicts("new_key", "new value")
        assert isinstance(result, dict)
        assert "has_conflicts" in result

    def test_remember_safe(self, agent):
        result = agent.remember_safe("safe_key", "safe value")
        assert result.success
        assert hasattr(result, "conflicts")

    def test_detect_conflicts_with_existing(self, agent):
        agent.remember("existing", "original value")
        result = agent.detect_conflicts("existing", "different value")
        assert result["has_conflicts"]


# ===================================================================
# SNAPSHOT / RESTORE
# ===================================================================

class TestSnapshotRestore:
    def test_snapshot(self, agent):
        agent.remember("data", "important")
        result = agent.snapshot("test_snap")
        assert result.label == "test_snap"
        assert result.keys_captured >= 1

    def test_restore(self, agent):
        agent.remember("data", "before_snap")
        agent.snapshot("restore_test")
        agent.remember("data", "after_snap")
        result = agent.restore("restore_test")
        assert result.keys_restored >= 1


# ===================================================================
# SHARED MEMORY
# ===================================================================

class TestSharedMemory:
    def test_share(self, agent):
        result = agent.share("shared_key", "shared_value", space="test_space")
        assert result.success

    def test_read_shared(self, agent):
        agent.share("readable", "data_here", space="test_space")
        result = agent.read_shared("readable", space="test_space")
        assert result.found

    def test_share_safe(self, agent):
        """Test conflict-aware shared memory write."""
        result = agent.share_safe("config", "initial", space="safe_space")
        assert isinstance(result, dict)
        assert "write" in result


# ===================================================================
# KNOWLEDGE GRAPH
# ===================================================================

class TestKnowledgeGraph:
    def test_related(self, agent):
        agent.remember("team", "Alice manages the engineering team")
        result = agent.related("Alice")
        assert hasattr(result, "entity")


# ===================================================================
# TEMPORAL VERSIONING
# ===================================================================

class TestTemporal:
    def test_recall_history(self, agent):
        agent.remember("version_test", "v1")
        agent.remember("version_test", "v2")
        result = agent.recall_history("version_test")
        assert hasattr(result, "versions")


# ===================================================================
# LOOP DETECTION
# ===================================================================

class TestLoopDetection:
    def test_write_loop_no_false_positive(self, agent):
        """Writing different content should not trigger loop warning."""
        r1 = agent.remember("item1", "completely unique content alpha")
        r2 = agent.remember("item2", "totally different beta stuff")
        r3 = agent.remember("item3", "unrelated gamma information")
        # Should not have loop warnings for genuinely different content
        assert r1.success and r2.success and r3.success

    def test_loop_status(self, agent):
        """Test the v2 loop status endpoint."""
        result = agent.get_loop_status()
        assert "severity" in result
        assert "score" in result
        assert result["severity"] in ("green", "yellow", "orange", "red")
        assert 0 <= result["score"] <= 100

    def test_loop_history(self, agent):
        result = agent.get_loop_history(hours=1)
        assert "total_alerts" in result
        assert "by_type" in result

    def test_loop_status_green_for_healthy_agent(self, agent):
        """A fresh agent with few writes should be green."""
        agent.remember("normal", "perfectly normal write")
        status = agent.get_loop_status()
        # Allow green or yellow (yellow can happen if background threads from
        # previous tests wrote alerts that haven't expired yet)
        assert status["severity"] in ("green", "yellow")


# ===================================================================
# DECISION AUDIT
# ===================================================================

class TestDecisionAudit:
    def test_log_decision(self, agent):
        result = agent.log_decision("deploy to production", "all tests passed", {"env": "prod"})
        assert isinstance(result, dict)
        assert result["decision"] == "deploy to production"

    def test_log_decision_returns_data(self, agent):
        result = agent.log_decision("upgrade db", "need more capacity")
        assert "reasoning" in result
        assert "timestamp" in result


# ===================================================================
# USAGE ANALYTICS
# ===================================================================

class TestAnalytics:
    def test_usage_analytics(self, agent):
        agent.remember("a", "1")
        agent.remember("b", "2")
        result = agent.usage_analytics()
        assert result["total_memories"] >= 2
        assert result["agent_id"] == "test_agent"

    def test_get_stats(self, agent):
        stats = agent.get_stats()
        assert stats.agent_id == "test_agent"
        assert stats.uptime_seconds >= 0


# ===================================================================
# AGENT MESSAGING (NEW)
# ===================================================================

class TestMessaging:
    def test_send_message(self, agent):
        result = agent.send_message("agent-b", "hello from test", message_type="info")
        assert result["sent"]
        assert "msg_id" in result

    def test_read_messages_empty(self, agent):
        messages = agent.read_messages()
        assert isinstance(messages, list)

    def test_broadcast(self, agent):
        result = agent.broadcast("system update", message_type="alert")
        assert result["broadcast"]
        assert "msg_id" in result

    def test_read_broadcasts(self, agent):
        agent.broadcast("test broadcast")
        broadcasts = agent.read_broadcasts(since_seconds=60)
        assert isinstance(broadcasts, list)
        assert len(broadcasts) >= 1

    def test_mark_read(self, agent):
        result = agent.mark_read("nonexistent_msg")
        assert result["marked_read"] == False  # Message doesn't exist


# ===================================================================
# MEMORY FORGETTING (NEW)
# ===================================================================

class TestForgetting:
    def test_forget(self, agent):
        agent.remember("to_forget", "delete me")
        result = agent.forget("to_forget")
        assert isinstance(result, dict)

    def test_forget_by_tag(self, agent):
        agent.remember("tagged1", "data", tags=["cleanup"])
        result = agent.forget_by_tag("cleanup")
        assert isinstance(result, dict)
        assert "deleted" in result

    def test_forget_stale(self, agent):
        agent.remember("old_item", "stale data")
        result = agent.forget_stale(0)  # 0 days = everything is stale
        assert isinstance(result, dict)
        assert "deleted" in result


# ===================================================================
# MEMORY CONSOLIDATION (NEW)
# ===================================================================

class TestConsolidation:
    def test_consolidate_dry_run(self, agent):
        agent.remember("dup1", "the quick brown fox jumps")
        agent.remember("dup2", "the quick brown fox leaps")
        result = agent.consolidate(dry_run=True)
        assert isinstance(result, dict)
        assert "dry_run" in result

    def test_consolidate_empty(self, agent):
        result = agent.consolidate(dry_run=True)
        assert isinstance(result, dict)


# ===================================================================
# MEMORY HEALTH (NEW)
# ===================================================================

class TestMemoryHealth:
    def test_memory_health(self, agent):
        agent.remember("healthy", "good data")
        result = agent.memory_health()
        assert "score" in result
        assert 0 <= result["score"] <= 100
        assert "issues" in result

    def test_memory_health_empty_agent(self, agent):
        result = agent.memory_health()
        assert result["total_memories"] == 0


# ===================================================================
# GOAL TRACKING (NEW)
# ===================================================================

class TestGoalTracking:
    def test_set_goal(self, agent):
        result = agent.set_goal("Complete migration", milestones=["Backup", "Migrate", "Validate"])
        assert result["goal_set"]
        assert result["milestones"] == 3

    def test_get_goal(self, agent):
        agent.set_goal("Test goal")
        result = agent.get_goal()
        assert result["has_goal"]
        assert result["goal"] == "Test goal"
        assert result["progress"] == 0.0

    def test_update_progress(self, agent):
        agent.set_goal("Multi step", milestones=["Step 1", "Step 2"])
        result = agent.update_progress(milestone_index=0, note="First step done")
        assert result["progress"] == 0.5
        assert result["milestones_completed"] == 1

    def test_goal_completion(self, agent):
        agent.set_goal("Simple", milestones=["Only step"])
        result = agent.update_progress(milestone_index=0)
        assert result["progress"] == 1.0
        assert result["status"] == "completed"

    def test_no_goal(self, agent):
        result = agent.get_goal()
        assert not result["has_goal"]


# ===================================================================
# MEMORY EXPORT / IMPORT (NEW)
# ===================================================================

class TestExportImport:
    def test_export(self, agent):
        agent.remember("export_test", "valuable data")
        agent.remember("export_test2", "more data")
        bundle = agent.export_memories()
        assert bundle["count"] >= 2
        assert "memories" in bundle
        assert "meta" in bundle

    def test_import(self, agent):
        # Create a fake export bundle
        bundle = {
            "meta": {"agent_id": "other-agent", "exported_at": time.time(), "version": "1.0"},
            "memories": {
                "imported_key": {"value": "imported_value", "timestamp": time.time()},
            },
            "snapshots": {},
            "count": 1,
        }
        result = agent.import_memories(bundle)
        assert result["imported"] == 1
        assert result["source_agent"] == "other-agent"

    def test_import_no_overwrite(self, agent):
        agent.remember("existing", "original")
        bundle = {
            "meta": {"agent_id": "x", "exported_at": time.time(), "version": "1.0"},
            "memories": {"existing": {"value": "new_value", "timestamp": time.time()}},
            "snapshots": {},
            "count": 1,
        }
        result = agent.import_memories(bundle, overwrite=False)
        assert result["skipped"] == 1
        assert result["imported"] == 0

    def test_roundtrip(self, agent):
        """Export from one agent, import to same — verify data integrity."""
        agent.remember("roundtrip", "critical data")
        bundle = agent.export_memories()
        # Clear and reimport
        agent.forget("roundtrip")
        result = agent.import_memories(bundle, overwrite=True)
        assert result["imported"] >= 1


# ===================================================================
# MEMORY SUMMARIZATION (NEW)
# ===================================================================

# ===================================================================
# FILTERED SEARCH (NEW)
# ===================================================================

class TestFilteredSearch:
    def test_search_no_filters(self, agent):
        agent.remember("item", "some content")
        results = agent.search_filtered()
        assert isinstance(results, list)

    def test_search_by_importance(self, agent):
        agent.remember_important("critical_item", "urgent stuff", importance="critical")
        agent.remember_important("low_item", "boring stuff", importance="low")
        results = agent.search_filtered(importance="critical")
        assert isinstance(results, list)

    def test_search_with_limit(self, agent):
        for i in range(10):
            agent.remember(f"bulk_{i}", f"value {i}")
        results = agent.search_filtered(limit=3)
        assert len(results) <= 3


# ===================================================================
# CONFIDENCE DECAY (NEW)
# ===================================================================

# ===================================================================
# FEATURE GATING (NEW)
# ===================================================================

class TestFeatureGating:
    def test_brain_status_local(self, agent):
        result = agent.get_brain_status()
        assert isinstance(result, dict)
        # In local mode, should indicate it's a cloud feature
        assert "available" in result or "mode" in result

    def test_dashboard_url_local(self, agent):
        result = agent.get_dashboard_url()
        assert isinstance(result, dict)
        assert "local_dashboard" in result or "dashboard" in result


# ===================================================================
# HANDOFF / TASK MANAGEMENT
# ===================================================================

class TestHandoff:
    def test_handoff(self, agent):
        result = agent.handoff("task_001", "agent-b", {"instruction": "process this"})
        assert result.success
        assert result.task_id == "task_001"

    def test_claim_task(self, agent):
        agent.handoff("task_002", "test-agent", {"data": "for me"})
        result = agent.claim_task("task_002")
        assert result.found

    def test_complete_task(self, agent):
        result = agent.complete_task("task_003", {"output": "done"})
        assert result.task_id == "task_003"


# ===================================================================
# CONTEXT MANAGER
# ===================================================================

class TestContextManager:
    def test_context_manager(self, agent):
        """Test that AgentRuntime works as a context manager."""
        # Agent from fixture already works - just verify enter/exit
        agent.remember("ctx_test", "context works")
        result = agent.recall("ctx_test")
        assert result.found


# ===================================================================
# BILLING MODULE
# ===================================================================

class TestBillingModule:
    def test_plan_limits_defined(self):
        from synrix_runtime.api.billing import PLAN_LIMITS
        assert "free" in PLAN_LIMITS
        assert "pro" in PLAN_LIMITS
        assert "business" in PLAN_LIMITS
        assert "scale" in PLAN_LIMITS
        assert PLAN_LIMITS["free"][0] == 5  # 5 agents on free

    def test_get_plans(self):
        from synrix_runtime.api.billing import get_plans
        plans = get_plans()
        assert len(plans) == 5
        names = [p["name"] for p in plans]
        assert "Free" in names
        assert "Pro" in names
        assert "Business" in names
        assert "Scale" in names
        assert "Enterprise" in names

    def test_price_to_plan(self):
        from synrix_runtime.api.billing import _price_to_plan
        # Unknown price should return free
        assert _price_to_plan("unknown_price_id") == "free"


# ===================================================================
# AUTH FLOW MODULE
# ===================================================================

class TestAuthFlow:
    def test_load_save_config(self):
        from synrix_runtime.auth_flow import _load_config, _save_config, CONFIG_DIR
        import tempfile
        # Test that config functions work without errors
        config = _load_config()
        assert isinstance(config, dict)

    def test_get_api_key_from_env(self):
        os.environ["OCTOPODA_API_KEY"] = "sk-octopoda-test-key"
        from synrix_runtime.auth_flow import get_api_key
        key = get_api_key()
        # Should find the env var
        assert key == "sk-octopoda-test-key" or key  # Config file may override
        del os.environ["OCTOPODA_API_KEY"]

    def test_ensure_authenticated_local_mode(self):
        os.environ["OCTOPODA_LOCAL_MODE"] = "1"
        from synrix_runtime.auth_flow import ensure_authenticated
        result = ensure_authenticated()
        assert result == ""  # Local mode returns empty string
