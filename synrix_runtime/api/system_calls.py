"""
Synrix Agent Runtime — System Calls
Low-level system operations for advanced users.
"""

import time
import json
from typing import Any, Dict, List, Optional


class SystemCalls:
    """Low-level system call interface to the Synrix runtime."""

    def __init__(self, backend=None):
        self.backend = backend
        if self.backend is None:
            from synrix.agent_backend import get_synrix_backend
            from synrix_runtime.config import SynrixConfig
            config = SynrixConfig.from_env()
            self.backend = get_synrix_backend(**config.get_backend_kwargs())

    def raw_write(self, key: str, value: Any, metadata: dict = None) -> dict:
        """Write directly to Synrix with full latency measurement."""
        start = time.perf_counter_ns()
        node_id = self.backend.write(key, value, metadata=metadata)
        latency_us = (time.perf_counter_ns() - start) / 1000
        return {"node_id": node_id, "key": key, "latency_us": latency_us, "success": node_id is not None}

    def raw_read(self, key: str) -> dict:
        """Read directly from Synrix with full latency measurement."""
        start = time.perf_counter_ns()
        result = self.backend.read(key)
        latency_us = (time.perf_counter_ns() - start) / 1000
        return {"result": result, "key": key, "latency_us": latency_us, "found": result is not None}

    def raw_query(self, prefix: str, limit: int = 100) -> dict:
        """Query Synrix by prefix with full latency measurement."""
        start = time.perf_counter_ns()
        results = self.backend.query_prefix(prefix, limit=limit)
        latency_us = (time.perf_counter_ns() - start) / 1000
        return {"results": results, "prefix": prefix, "count": len(results), "latency_us": latency_us}

    def get_system_info(self) -> dict:
        """Get runtime system information."""
        from synrix_runtime.core.daemon import RuntimeDaemon
        try:
            daemon = RuntimeDaemon.get_instance()
            return daemon.get_system_status()
        except Exception as e:
            return {"error": str(e), "status": "unavailable"}

    def force_snapshot(self, agent_id: str, label: str = None) -> dict:
        """Force a snapshot of an agent's state."""
        if label is None:
            label = f"forced_{int(time.time()*1000000)}"

        start = time.perf_counter_ns()
        all_keys = self.backend.query_prefix(f"agents:{agent_id}:", limit=500)
        snapshot_data = {}
        for item in all_keys:
            key = item.get("key", "")
            if ":snapshots:" not in key:
                data = item.get("data", {})
                snapshot_data[key] = data.get("value", data)

        self.backend.write(
            f"agents:{agent_id}:snapshots:{label}",
            {"label": label, "agent_id": agent_id, "keys": snapshot_data,
             "key_count": len(snapshot_data), "created_at": time.time()},
            metadata={"type": "snapshot"}
        )
        latency_us = (time.perf_counter_ns() - start) / 1000

        return {"label": label, "keys_captured": len(snapshot_data), "latency_us": latency_us}

    def simulate_crash(self, agent_id: str) -> dict:
        """Simulate a crash for an agent."""
        start = time.perf_counter_ns()
        self.backend.write(
            f"runtime:agents:{agent_id}:state",
            {"value": "crashed"},
            metadata={"type": "agent_state"}
        )
        ts = int(time.time() * 1000000)
        self.backend.write(
            f"runtime:events:crash:{agent_id}:{ts}",
            {"agent_id": agent_id, "reason": "simulated_crash", "timestamp": time.time()},
            metadata={"type": "crash_event"}
        )
        latency_us = (time.perf_counter_ns() - start) / 1000

        return {"agent_id": agent_id, "crashed": True, "latency_us": latency_us}

    def trigger_recovery(self, agent_id: str) -> dict:
        """Trigger recovery for a crashed agent."""
        from synrix_runtime.core.recovery import RecoveryOrchestrator
        orchestrator = RecoveryOrchestrator(self.backend)
        result = orchestrator.full_recovery(agent_id)
        return {
            "agent_id": agent_id,
            "recovery_time_us": result.recovery_time_us,
            "keys_restored": result.keys_restored,
            "snapshot_used": result.snapshot_used,
            "step_timings": result.step_timings,
        }

    def export_agent_state(self, agent_id: str) -> dict:
        """Export complete agent state for backup/analysis."""
        memory = self.backend.query_prefix(f"agents:{agent_id}:", limit=500)
        metrics = self.backend.query_prefix(f"metrics:{agent_id}:", limit=500)
        audit = self.backend.query_prefix(f"audit:{agent_id}:", limit=500)

        return {
            "agent_id": agent_id,
            "exported_at": time.time(),
            "memory_keys": len(memory),
            "metric_entries": len(metrics),
            "audit_entries": len(audit),
            "memory": memory,
            "metrics": metrics,
            "audit": audit,
        }

    def benchmark(self, iterations: int = 100) -> dict:
        """Run a quick performance benchmark against Synrix."""
        write_times = []
        read_times = []
        query_times = []

        for i in range(iterations):
            key = f"benchmark:test:{i}"
            s = time.perf_counter_ns()
            self.backend.write(key, {"iteration": i, "data": "x" * 100}, metadata={"type": "benchmark"})
            write_times.append((time.perf_counter_ns() - s) / 1000)

            s = time.perf_counter_ns()
            self.backend.read(key)
            read_times.append((time.perf_counter_ns() - s) / 1000)

        s = time.perf_counter_ns()
        self.backend.query_prefix("benchmark:test:", limit=iterations)
        query_times.append((time.perf_counter_ns() - s) / 1000)

        return {
            "iterations": iterations,
            "write_avg_us": sum(write_times) / len(write_times),
            "write_min_us": min(write_times),
            "write_max_us": max(write_times),
            "read_avg_us": sum(read_times) / len(read_times),
            "read_min_us": min(read_times),
            "read_max_us": max(read_times),
            "query_avg_us": sum(query_times) / len(query_times),
        }
