"""
Synrix Agent Runtime — Shared Memory Bus
Multi-agent coordination through shared persistent memory spaces.
"""

import time
import json
from typing import Any, Dict, List, Optional


class SharedMemoryBus:
    """Shared memory bus for multi-agent coordination via Synrix."""

    def __init__(self, backend=None):
        self.backend = backend
        if self.backend is None:
            from synrix.agent_backend import get_synrix_backend
            from synrix_runtime.config import SynrixConfig
            config = SynrixConfig.from_env()
            self.backend = get_synrix_backend(**config.get_backend_kwargs())

    def write(self, space: str, key: str, value: Any, author_agent: str) -> dict:
        """Write to a shared memory space."""
        full_key = f"shared:{space}:{key}"
        payload = value if isinstance(value, dict) else {"value": value}
        payload["_author"] = author_agent
        payload["_written_at"] = time.time()

        start = time.perf_counter_ns()
        node_id = self.backend.write(full_key, payload, metadata={"type": "shared_memory", "space": space, "author": author_agent})
        latency_us = (time.perf_counter_ns() - start) / 1000

        # Changelog entry
        ts = int(time.time() * 1000000)
        self.backend.write(
            f"shared:{space}:changelog:{ts}",
            {"key": key, "author": author_agent, "action": "write", "timestamp": time.time()},
            metadata={"type": "shared_changelog"}
        )

        return {"node_id": node_id, "key": key, "space": space, "latency_us": latency_us}

    def read(self, space: str, key: str) -> Optional[dict]:
        """Read from a shared memory space."""
        full_key = f"shared:{space}:{key}"
        start = time.perf_counter_ns()
        result = self.backend.read(full_key)
        latency_us = (time.perf_counter_ns() - start) / 1000

        if result:
            data = result.get("data", {})
            value = data.get("value", data)
            return {"key": key, "value": value, "latency_us": latency_us}
        return None

    def get_all(self, space: str) -> list:
        """Get everything in a shared space."""
        start = time.perf_counter_ns()
        results = self.backend.query_prefix(f"shared:{space}:", limit=500)
        latency_us = (time.perf_counter_ns() - start) / 1000

        items = []
        for r in results:
            key = r.get("key", "")
            if ":changelog:" in key:
                continue
            short_key = key.replace(f"shared:{space}:", "", 1)
            data = r.get("data", {})
            value = data.get("value", data)
            items.append({
                "key": short_key,
                "value": value,
                "author": value.get("_author") if isinstance(value, dict) else None,
                "node_id": r.get("id"),
            })
        return items

    def get_changelog(self, space: str, limit: int = 100) -> list:
        """Get chronological list of all writes to a space."""
        results = self.backend.query_prefix(f"shared:{space}:changelog:", limit=limit)
        changes = []
        for r in results:
            data = r.get("data", {})
            val = data.get("value", data)
            changes.append(val)
        changes.sort(key=lambda x: x.get("timestamp", 0) if isinstance(x, dict) else 0, reverse=True)
        return changes

    def list_spaces(self) -> list:
        """List all active shared memory spaces."""
        results = self.backend.query_prefix("shared:", limit=500)
        spaces = {}
        for r in results:
            key = r.get("key", "")
            parts = key.split(":")
            if len(parts) >= 2:
                space = parts[1]
                if space not in spaces:
                    spaces[space] = {"name": space, "key_count": 0, "agents": set()}
                if ":changelog:" not in key:
                    spaces[space]["key_count"] += 1
                data = r.get("data", {})
                val = data.get("value", data)
                if isinstance(val, dict) and "_author" in val:
                    spaces[space]["agents"].add(val["_author"])

        result = []
        for name, info in spaces.items():
            result.append({
                "name": name,
                "key_count": info["key_count"],
                "active_agents": list(info["agents"]),
                "agent_count": len(info["agents"]),
            })
        return result

    def get_bus_metrics(self) -> dict:
        """Get shared memory bus metrics."""
        spaces = self.list_spaces()
        total_keys = sum(s["key_count"] for s in spaces)
        all_agents = set()
        for s in spaces:
            all_agents.update(s["active_agents"])

        return {
            "total_spaces": len(spaces),
            "total_keys": total_keys,
            "total_agents": len(all_agents),
            "spaces": spaces,
            "most_active_space": max(spaces, key=lambda x: x["key_count"])["name"] if spaces else None,
        }
