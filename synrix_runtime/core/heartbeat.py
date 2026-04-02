"""
Synrix Agent Runtime — Heartbeat Manager
Per-agent heartbeat thread that writes to Synrix.
"""

import time
import threading
from typing import Optional


class HeartbeatManager:
    """Manages heartbeat threads for registered agents."""

    def __init__(self, backend=None):
        self.backend = backend
        if self.backend is None:
            from synrix.agent_backend import get_synrix_backend
            from synrix_runtime.config import SynrixConfig
            config = SynrixConfig.from_env()
            self.backend = get_synrix_backend(**config.get_backend_kwargs())
        self._threads = {}
        self._running = {}
        self._lock = threading.Lock()

    def start_heartbeat(self, agent_id: str, interval: float = 5.0):
        """Start a heartbeat thread for an agent."""
        with self._lock:
            if agent_id in self._running and self._running[agent_id]:
                return
            self._running[agent_id] = True

        def _beat():
            while self._running.get(agent_id, False):
                try:
                    now = time.time()
                    start = time.perf_counter_ns()
                    self.backend.write(
                        f"runtime:agents:{agent_id}:heartbeat",
                        {"value": now},
                        metadata={"type": "heartbeat"}
                    )
                    latency_us = (time.perf_counter_ns() - start) / 1000
                    self.backend.write(
                        f"runtime:agents:{agent_id}:last_active",
                        {"value": now},
                        metadata={"type": "timestamp"}
                    )
                except Exception:
                    pass
                time.sleep(interval)

        t = threading.Thread(target=_beat, name=f"heartbeat-{agent_id}", daemon=True)
        t.start()
        with self._lock:
            self._threads[agent_id] = t

    def stop_heartbeat(self, agent_id: str):
        """Stop the heartbeat thread for an agent."""
        with self._lock:
            self._running[agent_id] = False

    def stop_all(self):
        """Stop all heartbeat threads."""
        with self._lock:
            for agent_id in list(self._running.keys()):
                self._running[agent_id] = False

    def is_alive(self, agent_id: str) -> bool:
        """Check if an agent's heartbeat thread is running."""
        with self._lock:
            return self._running.get(agent_id, False)

    def get_last_heartbeat(self, agent_id: str) -> Optional[float]:
        """Get the last heartbeat timestamp for an agent."""
        result = self.backend.read(f"runtime:agents:{agent_id}:heartbeat")
        if result:
            data = result.get("data", {})
            val = data.get("value", data)
            if isinstance(val, dict):
                return val.get("value")
            return val
        return None

    def check_agent_health(self, agent_id: str, timeout: float = 10.0) -> dict:
        """Check health of an agent based on heartbeat."""
        last_beat = self.get_last_heartbeat(agent_id)
        now = time.time()

        if last_beat is None:
            return {"agent_id": agent_id, "healthy": False, "reason": "no_heartbeat"}

        age = now - last_beat
        healthy = age < timeout

        return {
            "agent_id": agent_id,
            "healthy": healthy,
            "last_heartbeat": last_beat,
            "age_seconds": round(age, 2),
            "timeout": timeout,
            "reason": "ok" if healthy else "heartbeat_timeout",
        }
