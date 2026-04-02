"""
Tests for RuntimeDaemon — the central nervous system.
"""

import time
import pytest


class TestDaemonLifecycle:

    def test_singleton(self, tmp_dir, monkeypatch):
        monkeypatch.setenv("SYNRIX_BACKEND", "sqlite")
        monkeypatch.setenv("SYNRIX_DATA_DIR", tmp_dir)

        from synrix_runtime.core.daemon import RuntimeDaemon
        RuntimeDaemon.reset_instance()
        d1 = RuntimeDaemon.get_instance()
        d2 = RuntimeDaemon.get_instance()
        assert d1 is d2
        RuntimeDaemon.reset_instance()

    def test_start_and_shutdown(self, daemon):
        assert daemon.running
        assert daemon.backend is not None
        assert daemon._boot_time is not None

    def test_register_agent(self, daemon):
        result = daemon.register_agent("agent_a", "researcher", {"version": "1.0"})
        assert result["registered"]
        assert result["agent_id"] == "agent_a"
        assert result["latency_us"] > 0

    def test_deregister_agent(self, daemon):
        daemon.register_agent("agent_b", "worker")
        daemon.deregister_agent("agent_b")
        state = daemon.get_agent_state("agent_b")
        assert state == "deregistered"

    def test_get_active_agents(self, daemon):
        daemon.register_agent("active_1", "type_a")
        daemon.register_agent("active_2", "type_b")
        daemon.register_agent("inactive", "type_c")
        daemon.deregister_agent("inactive")

        active = daemon.get_active_agents()
        active_ids = [a["agent_id"] for a in active]
        assert "active_1" in active_ids
        assert "active_2" in active_ids
        assert "inactive" not in active_ids

    def test_recover_agent(self, daemon):
        daemon.register_agent("crash_agent", "worker")
        # Write some memory
        daemon.backend.write("agents:crash_agent:data", {"value": "important"})

        result = daemon.recover_agent("crash_agent")
        assert result["agent_id"] == "crash_agent"
        assert result["recovery_time_us"] > 0
        assert result["keys_restored"] >= 1

    def test_get_system_status(self, daemon):
        daemon.register_agent("status_agent", "bot")
        status = daemon.get_system_status()
        assert status["status"] == "running"
        assert status["active_agents"] >= 1
        assert status["version"] == "1.0.0"
        assert status["uptime_seconds"] >= 0

    def test_event_listeners(self, daemon):
        events = []
        daemon.add_event_listener(lambda e: events.append(e))
        daemon.register_agent("evt_agent", "test")

        assert len(events) >= 1
        assert events[0]["event_type"] == "agent_registered"

        daemon.remove_event_listener(events.append)
