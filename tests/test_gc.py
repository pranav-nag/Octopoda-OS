"""
Tests for the Garbage Collector.
"""

import os
import time
import json
import pytest


@pytest.fixture
def gc_backend(tmp_dir, monkeypatch):
    """Provide a backend with test data for GC tests."""
    monkeypatch.setenv("SYNRIX_BACKEND", "sqlite")
    monkeypatch.setenv("SYNRIX_DATA_DIR", tmp_dir)

    from synrix.agent_backend import get_synrix_backend
    backend = get_synrix_backend(
        backend="sqlite",
        sqlite_path=os.path.join(tmp_dir, "gc_test.db"),
    )
    yield backend
    backend.close()


def _write_old_entry(backend, key, days_old):
    """Write an entry and manually backdate its updated_at timestamp."""
    backend.write(key, {"value": f"old_{days_old}d"})
    # Backdate the entry directly in SQLite
    cutoff = time.time() - (days_old * 86400)
    conn = backend.client._get_conn()
    try:
        conn.execute(
            "UPDATE nodes SET updated_at = ? WHERE name = ? AND collection = ?",
            (cutoff, key, backend.collection),
        )
        conn.commit()
    finally:
        conn.close()


class TestGCConfig:

    def test_default_config(self):
        from synrix_runtime.core.gc import GCConfig

        cfg = GCConfig()
        assert cfg.enabled is True
        assert cfg.interval_hours == 6
        assert cfg.metrics_days == 7
        assert cfg.events_days == 14
        assert cfg.audit_days == 90
        assert cfg.max_snapshots_per_agent == 10

    def test_config_from_env(self, monkeypatch):
        from synrix_runtime.core.gc import GCConfig

        monkeypatch.setenv("SYNRIX_GC_ENABLED", "false")
        monkeypatch.setenv("SYNRIX_GC_METRICS_DAYS", "3")
        monkeypatch.setenv("SYNRIX_GC_AUDIT_DAYS", "30")

        cfg = GCConfig.from_env()
        assert cfg.enabled is False
        assert cfg.metrics_days == 3
        assert cfg.audit_days == 30


class TestGCPruning:

    def test_prune_old_metrics(self, gc_backend):
        from synrix_runtime.core.gc import GCConfig, GarbageCollector

        # Write metrics: 2 old (10 days), 1 recent (1 day)
        _write_old_entry(gc_backend, "metrics:cpu:1", days_old=10)
        _write_old_entry(gc_backend, "metrics:mem:2", days_old=10)
        _write_old_entry(gc_backend, "metrics:cpu:3", days_old=1)

        config = GCConfig(metrics_days=7, events_days=0, alerts_days=0, audit_days=0, max_snapshots_per_agent=0)
        gc = GarbageCollector(gc_backend, config)
        stats = gc.run_gc()

        assert stats["metrics_deleted"] == 2

    def test_keep_recent_metrics(self, gc_backend):
        from synrix_runtime.core.gc import GCConfig, GarbageCollector

        # All entries are recent
        gc_backend.write("metrics:cpu:fresh1", {"value": 42})
        gc_backend.write("metrics:cpu:fresh2", {"value": 43})

        config = GCConfig(metrics_days=7, events_days=0, alerts_days=0, audit_days=0, max_snapshots_per_agent=0)
        gc = GarbageCollector(gc_backend, config)
        stats = gc.run_gc()

        assert stats["metrics_deleted"] == 0

    def test_prune_old_events(self, gc_backend):
        from synrix_runtime.core.gc import GCConfig, GarbageCollector

        _write_old_entry(gc_backend, "runtime:events:crash:1", days_old=20)
        _write_old_entry(gc_backend, "runtime:events:crash:2", days_old=1)

        config = GCConfig(metrics_days=0, events_days=14, alerts_days=0, audit_days=0, max_snapshots_per_agent=0)
        gc = GarbageCollector(gc_backend, config)
        stats = gc.run_gc()

        assert stats["events_deleted"] == 1

    def test_prune_old_audit(self, gc_backend):
        from synrix_runtime.core.gc import GCConfig, GarbageCollector

        _write_old_entry(gc_backend, "audit:decision:1", days_old=100)
        _write_old_entry(gc_backend, "audit:decision:2", days_old=100)
        _write_old_entry(gc_backend, "audit:decision:3", days_old=30)

        config = GCConfig(metrics_days=0, events_days=0, alerts_days=0, audit_days=90, max_snapshots_per_agent=0)
        gc = GarbageCollector(gc_backend, config)
        stats = gc.run_gc()

        assert stats["audit_deleted"] == 2

    def test_gc_on_empty_database(self, gc_backend):
        from synrix_runtime.core.gc import GCConfig, GarbageCollector

        config = GCConfig()
        gc = GarbageCollector(gc_backend, config)
        stats = gc.run_gc()

        assert stats["metrics_deleted"] == 0
        assert stats["events_deleted"] == 0
        assert stats["alerts_deleted"] == 0
        assert stats["audit_deleted"] == 0
        assert stats["snapshots_pruned"] == 0
        assert stats["elapsed_ms"] >= 0

    def test_vacuum_after_large_delete(self, gc_backend):
        from synrix_runtime.core.gc import GCConfig, GarbageCollector

        # Write 1100 old metrics to trigger vacuum threshold (>1000)
        for i in range(1100):
            _write_old_entry(gc_backend, f"metrics:bulk:{i}", days_old=10)

        config = GCConfig(metrics_days=7, events_days=0, alerts_days=0, audit_days=0, max_snapshots_per_agent=0)
        gc = GarbageCollector(gc_backend, config)
        stats = gc.run_gc()

        assert stats["metrics_deleted"] == 1100
        assert stats.get("vacuumed") is True


class TestSnapshotPruning:

    def test_prune_old_snapshots(self, gc_backend):
        from synrix_runtime.core.gc import GCConfig, GarbageCollector

        # Write 15 snapshots for one agent (max 10)
        for i in range(15):
            gc_backend.write(
                f"agents:agentX:snapshots:snap_{i}",
                {"value": {"created_at": time.time() - (15 - i) * 60, "label": f"snap_{i}"}},
            )

        config = GCConfig(metrics_days=0, events_days=0, alerts_days=0, audit_days=0, max_snapshots_per_agent=10)
        gc = GarbageCollector(gc_backend, config)
        stats = gc.run_gc()

        assert stats["snapshots_pruned"] == 5

    def test_keep_snapshots_under_limit(self, gc_backend):
        from synrix_runtime.core.gc import GCConfig, GarbageCollector

        # Write only 3 snapshots (under limit of 10)
        for i in range(3):
            gc_backend.write(
                f"agents:agentY:snapshots:snap_{i}",
                {"value": {"created_at": time.time() - i * 60, "label": f"snap_{i}"}},
            )

        config = GCConfig(metrics_days=0, events_days=0, alerts_days=0, audit_days=0, max_snapshots_per_agent=10)
        gc = GarbageCollector(gc_backend, config)
        stats = gc.run_gc()

        assert stats["snapshots_pruned"] == 0
