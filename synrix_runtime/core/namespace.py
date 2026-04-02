"""
Synrix Agent Runtime — Namespace Manager
Manages key namespace hierarchy for organized memory access.
"""

import time
from typing import Dict, List, Optional


NAMESPACES = {
    "agents": "Agent private memory — agents:{agent_id}:{key}",
    "shared": "Shared memory bus — shared:{space}:{key}",
    "tasks": "Task handoff and completion — tasks:{type}:{task_id}",
    "metrics": "Performance metrics — metrics:{agent_id}:{metric_type}:{timestamp}",
    "audit": "Audit trail — audit:{agent_id}:{timestamp}:{event_type}",
    "runtime": "Runtime system state — runtime:{subsystem}:{key}",
    "alerts": "Anomaly alerts — alerts:{agent_id}:{timestamp}",
}


class NamespaceManager:
    """Manages hierarchical key namespaces in Synrix."""

    def __init__(self, backend=None):
        self.backend = backend
        if self.backend is None:
            from synrix.agent_backend import get_synrix_backend
            from synrix_runtime.config import SynrixConfig
            config = SynrixConfig.from_env()
            self.backend = get_synrix_backend(**config.get_backend_kwargs())

    def list_namespaces(self) -> List[dict]:
        """List all top-level namespaces with descriptions and key counts."""
        result = []
        for ns, desc in NAMESPACES.items():
            start = time.perf_counter_ns()
            keys = self.backend.query_prefix(f"{ns}:", limit=1)
            latency_us = (time.perf_counter_ns() - start) / 1000
            result.append({
                "namespace": ns,
                "description": desc,
                "has_data": len(keys) > 0,
                "query_latency_us": latency_us,
            })
        return result

    def browse(self, prefix: str, limit: int = 100) -> List[dict]:
        """Browse keys under a given prefix."""
        start = time.perf_counter_ns()
        results = self.backend.query_prefix(prefix, limit=limit)
        latency_us = (time.perf_counter_ns() - start) / 1000

        items = []
        for r in results:
            key = r.get("key", "")
            data = r.get("data", {})
            value = data.get("value", data)
            items.append({
                "key": key,
                "value": value,
                "node_id": r.get("id"),
                "size_bytes": len(str(value).encode()),
            })
        return items

    def get_tree(self, prefix: str = "", depth: int = 2) -> dict:
        """Get a tree structure of namespaces up to a certain depth."""
        results = self.backend.query_prefix(prefix, limit=500)
        tree = {}
        for r in results:
            key = r.get("key", "")
            parts = key.split(":")
            current = tree
            for i, part in enumerate(parts[:depth]):
                if part not in current:
                    current[part] = {"_count": 0, "_children": {}}
                current[part]["_count"] += 1
                current = current[part]["_children"]
        return tree

    def search(self, prefix: str, limit: int = 50) -> dict:
        """Search across all namespaces with a prefix."""
        start = time.perf_counter_ns()
        results = self.backend.query_prefix(prefix, limit=limit)
        latency_us = (time.perf_counter_ns() - start) / 1000

        return {
            "query": prefix,
            "results": results,
            "count": len(results),
            "latency_us": latency_us,
        }

    def get_agent_namespace(self, agent_id: str) -> List[dict]:
        """Get all keys in an agent's private namespace."""
        return self.browse(f"agents:{agent_id}:", limit=200)

    def get_shared_spaces(self) -> List[str]:
        """List all shared memory spaces."""
        results = self.backend.query_prefix("shared:", limit=500)
        spaces = set()
        for r in results:
            key = r.get("key", "")
            parts = key.split(":")
            if len(parts) >= 2:
                space = parts[1]
                if space != "changelog":
                    spaces.add(space)
        return sorted(spaces)
