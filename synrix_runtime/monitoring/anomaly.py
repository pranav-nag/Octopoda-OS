"""
Synrix Agent Runtime — Anomaly Detection
Detects performance anomalies and crash loops.
"""

import time
import math
from typing import Dict, List, Optional


class AnomalyDetector:
    """Detects anomalies by comparing current metrics against baselines."""

    def __init__(self, backend=None):
        self.backend = backend
        if self.backend is None:
            from synrix.agent_backend import get_synrix_backend
            from synrix_runtime.config import SynrixConfig
            config = SynrixConfig.from_env()
            self.backend = get_synrix_backend(**config.get_backend_kwargs())

    def establish_baseline(self, agent_id: str) -> dict:
        """Establish a performance baseline from the last 100 operations."""
        writes = self.backend.query_prefix(f"metrics:{agent_id}:write:", limit=100)
        reads = self.backend.query_prefix(f"metrics:{agent_id}:read:", limit=100)

        latencies = []
        for item in writes + reads:
            data = item.get("data", {})
            val = data.get("value", data)
            lat = val.get("latency_us", 0) if isinstance(val, dict) else 0
            if lat > 0:
                latencies.append(lat)

        if not latencies:
            baseline = {"mean_latency": 0, "std_dev": 0, "sample_size": 0, "ops_per_minute": 0}
        else:
            mean = sum(latencies) / len(latencies)
            variance = sum((x - mean) ** 2 for x in latencies) / len(latencies) if len(latencies) > 1 else 0
            std_dev = math.sqrt(variance)
            baseline = {
                "mean_latency": mean,
                "std_dev": std_dev,
                "sample_size": len(latencies),
                "ops_per_minute": len(latencies) / 5.0,
                "error_rate_baseline": 0.01,
                "timestamp": time.time(),
            }

        self.backend.write(
            f"runtime:baselines:{agent_id}",
            baseline,
            metadata={"type": "baseline"}
        )
        return baseline

    def _get_baseline(self, agent_id: str) -> dict:
        """Get stored baseline for an agent."""
        result = self.backend.read(f"runtime:baselines:{agent_id}")
        if result:
            data = result.get("data", {})
            val = data.get("value", data)
            return val if isinstance(val, dict) else {}
        return {}

    def check_for_anomalies(self, agent_id: str) -> list:
        """Check for anomalies against baseline."""
        baseline = self._get_baseline(agent_id)
        if not baseline or baseline.get("sample_size", 0) == 0:
            self.establish_baseline(agent_id)
            baseline = self._get_baseline(agent_id)
            if not baseline:
                return []

        anomalies = []
        now = time.time()
        cutoff = now - 300  # Last 5 minutes

        # Get recent operations
        recent_writes = self.backend.query_prefix(f"metrics:{agent_id}:write:", limit=100)
        recent_reads = self.backend.query_prefix(f"metrics:{agent_id}:read:", limit=100)

        recent_latencies = []
        recent_errors = 0
        recent_total = 0
        for item in recent_writes + recent_reads:
            data = item.get("data", {})
            val = data.get("value", data)
            if isinstance(val, dict):
                ts = val.get("timestamp", 0)
                if ts >= cutoff:
                    recent_total += 1
                    lat = val.get("latency_us", 0)
                    if lat > 0:
                        recent_latencies.append(lat)
                    if not val.get("success", True) or not val.get("found", True):
                        recent_errors += 1

        mean_baseline = baseline.get("mean_latency", 0)
        std_dev = baseline.get("std_dev", 1)

        # Check 1: Latency spike (> mean + 3*std_dev)
        if recent_latencies:
            recent_mean = sum(recent_latencies) / len(recent_latencies)
            threshold = mean_baseline + 3 * std_dev if std_dev > 0 else mean_baseline * 3
            if threshold > 0 and recent_mean > threshold:
                anomaly = {
                    "agent_id": agent_id,
                    "type": "latency_spike",
                    "severity": "warning",
                    "detail": f"Avg latency {recent_mean:.1f}us exceeds threshold {threshold:.1f}us",
                    "current_value": recent_mean,
                    "threshold": threshold,
                    "timestamp": now,
                }
                anomalies.append(anomaly)

        # Check 2: High error rate (> 5x baseline)
        if recent_total > 0:
            error_rate = recent_errors / recent_total
            baseline_error = baseline.get("error_rate_baseline", 0.01)
            if error_rate > baseline_error * 5:
                anomaly = {
                    "agent_id": agent_id,
                    "type": "high_error_rate",
                    "severity": "critical",
                    "detail": f"Error rate {error_rate:.2%} is {error_rate/max(baseline_error,0.001):.1f}x baseline",
                    "current_value": error_rate,
                    "threshold": baseline_error * 5,
                    "timestamp": now,
                }
                anomalies.append(anomaly)

        # Check 3: Idle anomaly (near zero ops/minute)
        ops_baseline = baseline.get("ops_per_minute", 0)
        recent_opm = recent_total / 5.0
        if ops_baseline > 1 and recent_opm < 0.1:
            anomaly = {
                "agent_id": agent_id,
                "type": "idle_anomaly",
                "severity": "info",
                "detail": f"Operations dropped to {recent_opm:.1f}/min from baseline {ops_baseline:.1f}/min",
                "current_value": recent_opm,
                "threshold": 0.1,
                "timestamp": now,
            }
            anomalies.append(anomaly)

        # Check 4: Crash loop (3+ crashes in 10 minutes)
        recent_crashes = self.backend.query_prefix(f"metrics:{agent_id}:crash:", limit=50)
        crash_in_window = 0
        for c in recent_crashes:
            data = c.get("data", {})
            val = data.get("value", data)
            ts = val.get("timestamp", 0) if isinstance(val, dict) else 0
            if ts > now - 600:
                crash_in_window += 1
        if crash_in_window >= 3:
            anomaly = {
                "agent_id": agent_id,
                "type": "crash_loop",
                "severity": "critical",
                "detail": f"{crash_in_window} crashes in last 10 minutes",
                "current_value": crash_in_window,
                "threshold": 3,
                "timestamp": now,
            }
            anomalies.append(anomaly)

        # Write anomalies to Synrix
        for anomaly in anomalies:
            ts = int(now * 1000000)
            self.backend.write(
                f"alerts:{agent_id}:{ts}",
                anomaly,
                metadata={"type": "anomaly_alert"}
            )

        return anomalies

    def get_all_anomalies(self) -> list:
        """Get all anomalies across all agents."""
        results = self.backend.query_prefix("alerts:", limit=200)
        anomalies = []
        for r in results:
            data = r.get("data", {})
            val = data.get("value", data)
            anomalies.append(val)
        anomalies.sort(key=lambda x: x.get("timestamp", 0) if isinstance(x, dict) else 0, reverse=True)
        return anomalies

    def get_agent_anomaly_history(self, agent_id: str) -> list:
        """Get anomaly history for a specific agent."""
        results = self.backend.query_prefix(f"alerts:{agent_id}:", limit=100)
        anomalies = []
        for r in results:
            data = r.get("data", {})
            val = data.get("value", data)
            anomalies.append(val)
        anomalies.sort(key=lambda x: x.get("timestamp", 0) if isinstance(x, dict) else 0, reverse=True)
        return anomalies
