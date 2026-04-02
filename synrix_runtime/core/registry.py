"""
Synrix Agent Runtime — Agent Registry
Manages agent registration, discovery, and lifecycle tracking.
"""

import time
import threading
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor


class AgentRegistry:
    """Registry for all agents in the runtime, backed by Synrix."""

    def __init__(self, backend=None):
        self.backend = backend
        if self.backend is None:
            from synrix.agent_backend import get_synrix_backend
            from synrix_runtime.config import SynrixConfig
            config = SynrixConfig.from_env()
            self.backend = get_synrix_backend(**config.get_backend_kwargs())
        self._local_cache = {}
        self._cache_lock = threading.Lock()

    def register(self, agent_id: str, agent_type: str = "generic", metadata: dict = None) -> dict:
        """Register a new agent and write all profile keys to Synrix."""
        metadata = metadata or {}
        now = time.time()
        start = time.perf_counter_ns()

        profile = {
            "agent_id": agent_id,
            "agent_type": agent_type,
            "metadata": metadata,
            "registered_at": now,
            "state": "running",
        }

        writes = [
            (f"runtime:agents:{agent_id}:profile", profile, {"type": "agent_profile"}),
            (f"runtime:agents:{agent_id}:state", {"value": "running"}, {"type": "agent_state"}),
            (f"runtime:agents:{agent_id}:type", {"value": agent_type}, {"type": "agent_type"}),
            (f"runtime:agents:{agent_id}:heartbeat", {"value": now}, {"type": "heartbeat"}),
            (f"runtime:agents:{agent_id}:registered_at", {"value": now}, {"type": "timestamp"}),
            (f"runtime:agents:{agent_id}:last_active", {"value": now}, {"type": "timestamp"}),
            (f"runtime:agents:{agent_id}:stats", {"writes": 0, "reads": 0, "queries": 0, "crashes": 0, "recoveries": 0}, {"type": "agent_stats"}),
            (f"runtime:agents:{agent_id}:metadata", metadata, {"type": "agent_metadata"}),
        ]
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda w: self.backend.write(w[0], w[1], metadata=w[2]), writes))

        latency_us = (time.perf_counter_ns() - start) / 1000

        with self._cache_lock:
            self._local_cache[agent_id] = profile

        return {"agent_id": agent_id, "registered": True, "latency_us": latency_us}

    def deregister(self, agent_id: str):
        """Mark agent as deregistered without deleting data."""
        self.backend.write(f"runtime:agents:{agent_id}:state", {"value": "deregistered"}, metadata={"type": "agent_state"})
        with self._cache_lock:
            if agent_id in self._local_cache:
                self._local_cache[agent_id]["state"] = "deregistered"

    def get_agent(self, agent_id: str) -> Optional[dict]:
        """Get full profile for a single agent."""
        result = self.backend.read(f"runtime:agents:{agent_id}:profile")
        if result:
            data = result.get("data", {})
            return data.get("value", data)
        return None

    def get_all(self) -> List[dict]:
        """Get all registered agents."""
        results = self.backend.query_prefix("runtime:agents:", limit=500)
        agents = {}
        for r in results:
            key = r.get("key", "")
            parts = key.split(":")
            if len(parts) >= 4 and parts[2] not in ("system",):
                agent_id = parts[2]
                if agent_id not in agents:
                    agents[agent_id] = {"agent_id": agent_id}
                field = parts[3]
                data = r.get("data", {})
                value = data.get("value", data)
                if isinstance(value, dict) and "value" in value:
                    value = value["value"]
                agents[agent_id][field] = value
        return list(agents.values())

    def get_active(self) -> List[dict]:
        """Get only active (non-deregistered) agents."""
        return [a for a in self.get_all() if a.get("state") != "deregistered"]

    def get_by_type(self, agent_type: str) -> List[dict]:
        """Get all agents of a specific type."""
        return [a for a in self.get_all() if a.get("type") == agent_type]

    def get_count(self) -> int:
        """Get count of active agents."""
        return len(self.get_active())

    def is_registered(self, agent_id: str) -> bool:
        """Check if an agent is currently registered and active."""
        with self._cache_lock:
            if agent_id in self._local_cache:
                return self._local_cache[agent_id].get("state") != "deregistered"
        agent = self.get_agent(agent_id)
        return agent is not None
