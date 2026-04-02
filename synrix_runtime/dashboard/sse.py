"""
Synrix Agent Runtime — SSE Event Stream
Server-Sent Events for real-time dashboard updates.
"""

import time
import json
import threading
from typing import Generator


class SSEManager:
    """Manages Server-Sent Events for the dashboard."""

    def __init__(self, backend=None):
        self.backend = backend
        if self.backend is None:
            from synrix.agent_backend import get_synrix_backend
            from synrix_runtime.config import SynrixConfig
            config = SynrixConfig.from_env()
            self.backend = get_synrix_backend(**config.get_backend_kwargs())
        self._last_event_ts = time.time()

    def event_stream(self) -> Generator:
        """Generate SSE events by polling Synrix every second."""
        while True:
            try:
                events = self._gather_events()
                for event in events:
                    event_type = event.get("type", "update")
                    data = json.dumps(event.get("data", {}))
                    yield f"event: {event_type}\ndata: {data}\n\n"
                self._last_event_ts = time.time()
            except GeneratorExit:
                break
            except Exception as e:
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
            time.sleep(1)

    def _gather_events(self) -> list:
        """Gather all current state for SSE emission."""
        events = []

        # Agent update
        try:
            from synrix_runtime.core.daemon import RuntimeDaemon
            daemon = RuntimeDaemon.get_instance()
            agents = daemon.get_active_agents()
            # Enrich with metrics so the frontend has ops/latency/score
            try:
                from synrix_runtime.monitoring.metrics import MetricsCollector
                collector = MetricsCollector.get_instance(self.backend)
                for a in agents:
                    agent_id = a.get("agent_id", "")
                    try:
                        m = collector.get_agent_metrics(agent_id)
                        a["performance_score"] = m.performance_score
                        a["total_operations"] = m.total_operations
                        a["avg_write_latency_us"] = m.avg_write_latency_us
                        a["avg_read_latency_us"] = m.avg_read_latency_us
                        a["memory_node_count"] = m.memory_node_count
                        a["crash_count"] = m.crash_count
                        a["uptime_seconds"] = m.uptime_seconds
                        a["error_rate"] = m.error_rate
                    except Exception:
                        pass
                    a["status"] = a.get("state", "unknown")
            except Exception:
                for a in agents:
                    a["status"] = a.get("state", "unknown")
            events.append({
                "type": "agent_update",
                "data": {"agents": agents, "timestamp": time.time()},
            })
        except Exception:
            events.append({"type": "agent_update", "data": {"agents": [], "timestamp": time.time()}})

        # Metrics update
        try:
            from synrix_runtime.monitoring.metrics import MetricsCollector
            collector = MetricsCollector.get_instance(self.backend)
            system = collector.get_system_metrics()
            events.append({
                "type": "metrics_update",
                "data": {
                    "total_agents": system.total_agents,
                    "active_agents": system.active_agents,
                    "total_operations": system.total_operations,
                    "mean_recovery_time_us": system.mean_recovery_time_us,
                    "total_crashes": system.total_crashes,
                    "total_recoveries": system.total_recoveries,
                    "uptime_seconds": system.system_uptime_seconds,
                    "timestamp": time.time(),
                },
            })
        except Exception:
            pass

        # Recent memory operations
        try:
            recent_ops = self.backend.query_prefix("metrics:", limit=20)
            memory_ops = []
            for op in recent_ops:
                data = op.get("data", {})
                val = data.get("value", data)
                if isinstance(val, dict):
                    memory_ops.append({
                        "key": op.get("key", ""),
                        "latency_us": val.get("latency_us", 0),
                        "timestamp": val.get("timestamp", 0),
                    })
            memory_ops.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
            events.append({
                "type": "memory_update",
                "data": {"operations": memory_ops[:10], "timestamp": time.time()},
            })
        except Exception:
            pass

        # Anomalies
        try:
            from synrix_runtime.monitoring.anomaly import AnomalyDetector
            detector = AnomalyDetector(self.backend)
            anomalies = detector.get_all_anomalies()
            if anomalies:
                events.append({
                    "type": "anomaly_alert",
                    "data": {"anomalies": anomalies[:5], "timestamp": time.time()},
                })
        except Exception:
            pass

        # Recovery events
        try:
            from synrix_runtime.core.recovery import RecoveryOrchestrator
            orchestrator = RecoveryOrchestrator(self.backend)
            recoveries = orchestrator.get_all_recovery_history()
            recent_recoveries = [r for r in recoveries if isinstance(r, dict) and r.get("timestamp", 0) > self._last_event_ts - 10]
            if recent_recoveries:
                events.append({
                    "type": "recovery_event",
                    "data": {"recoveries": recent_recoveries, "timestamp": time.time()},
                })
        except Exception:
            pass

        # System heartbeat
        events.append({
            "type": "system_heartbeat",
            "data": {"alive": True, "timestamp": time.time()},
        })

        return events
