"""
Synrix Agent Runtime — Performance Monitor
Real-time performance tracking and benchmarking.
"""

import time
from typing import Dict, List


class PerformanceMonitor:
    """Tracks and reports on runtime performance."""

    def __init__(self, backend=None):
        self.backend = backend
        if self.backend is None:
            from synrix.agent_backend import get_synrix_backend
            from synrix_runtime.config import SynrixConfig
            config = SynrixConfig.from_env()
            self.backend = get_synrix_backend(**config.get_backend_kwargs())

    def get_latency_percentiles(self, agent_id: str, metric_type: str = "write") -> dict:
        """Calculate latency percentiles for an agent."""
        results = self.backend.query_prefix(f"metrics:{agent_id}:{metric_type}:", limit=500)
        latencies = []
        for r in results:
            data = r.get("data", {})
            val = data.get("value", data)
            lat = val.get("latency_us", 0) if isinstance(val, dict) else 0
            if lat > 0:
                latencies.append(lat)

        if not latencies:
            return {"p50": 0, "p90": 0, "p95": 0, "p99": 0, "min": 0, "max": 0, "count": 0}

        latencies.sort()
        n = len(latencies)
        return {
            "p50": latencies[int(n * 0.5)],
            "p90": latencies[int(n * 0.9)],
            "p95": latencies[int(n * 0.95)],
            "p99": latencies[min(int(n * 0.99), n - 1)],
            "min": latencies[0],
            "max": latencies[-1],
            "mean": sum(latencies) / n,
            "count": n,
        }

    def get_throughput(self, agent_id: str, window_minutes: int = 5) -> dict:
        """Get operations throughput for an agent."""
        cutoff = time.time() - (window_minutes * 60)
        ops = {"write": 0, "read": 0, "query": 0}

        for op_type in ops:
            results = self.backend.query_prefix(f"metrics:{agent_id}:{op_type}:", limit=500)
            for r in results:
                data = r.get("data", {})
                val = data.get("value", data)
                ts = val.get("timestamp", 0) if isinstance(val, dict) else 0
                if ts >= cutoff:
                    ops[op_type] += 1

        total = sum(ops.values())
        return {
            "window_minutes": window_minutes,
            "total_ops": total,
            "ops_per_minute": total / window_minutes if window_minutes > 0 else 0,
            "breakdown": ops,
        }

    def compare_agents(self) -> list:
        """Compare performance across all agents."""
        from synrix_runtime.monitoring.metrics import MetricsCollector
        collector = MetricsCollector.get_instance(self.backend)
        return collector.get_agent_comparison()

    def get_system_health(self) -> dict:
        """Get overall system health score."""
        from synrix_runtime.monitoring.metrics import MetricsCollector
        collector = MetricsCollector.get_instance(self.backend)
        system = collector.get_system_metrics()
        comparison = collector.get_agent_comparison()

        if comparison:
            avg_score = sum(a["performance_score"] for a in comparison) / len(comparison)
        else:
            avg_score = 100.0

        health = "healthy"
        if avg_score < 50:
            health = "critical"
        elif avg_score < 75:
            health = "degraded"

        return {
            "health": health,
            "avg_performance_score": round(avg_score, 1),
            "active_agents": system.active_agents,
            "total_operations": system.total_operations,
            "total_crashes": system.total_crashes,
            "total_recoveries": system.total_recoveries,
            "uptime_seconds": system.system_uptime_seconds,
        }

    def run_benchmark(self, iterations: int = 50) -> dict:
        """Run a performance benchmark."""
        from synrix_runtime.api.system_calls import SystemCalls
        syscalls = SystemCalls(self.backend)
        return syscalls.benchmark(iterations)
