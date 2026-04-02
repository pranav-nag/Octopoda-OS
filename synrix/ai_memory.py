"""
AI Memory interface for SYNRIX.

Provides add/query/count API used by robotics and other high-level modules.
Wraps RawSynrixBackend.

Usage:
    from synrix.ai_memory import get_ai_memory

    memory = get_ai_memory()
    memory.add("key", "value")
    results = memory.query("prefix")
"""

from typing import Optional, Dict, List, Any
from pathlib import Path

try:
    from .raw_backend import RawSynrixBackend
except ImportError:
    RawSynrixBackend = None


class AIMemory:
    """Direct AI access to SYNRIX memory. Uses raw_backend (add_node / find_by_prefix)."""

    def __init__(self, lattice_path: Optional[str] = None, max_nodes: int = 100000):
        self.lattice_path = lattice_path or str(Path.home() / ".synrix_ai_memory.lattice")
        if RawSynrixBackend is None:
            raise ImportError("RawSynrixBackend not available. Install the Synrix engine and set SYNRIX_LIB_PATH.")
        self.backend = RawSynrixBackend(self.lattice_path, max_nodes=max_nodes, evaluation_mode=True)

    def add(self, name: str, data: str) -> Optional[int]:
        """Add a memory. Returns node ID or None."""
        try:
            node_id = self.backend.add_node(name, data, node_type=5)  # LATTICE_NODE_LEARNING
            if node_id is not None:
                self.backend.save()
            return node_id
        except Exception:
            return None

    def get(self, node_id: int) -> Optional[Dict[str, Any]]:
        """Get a node by ID."""
        try:
            node = self.backend.get_node(node_id)
            if node:
                return {"id": node.get("id"), "name": node.get("name"), "data": node.get("data")}
        except Exception:
            pass
        return None

    def query(self, prefix: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Query by prefix. Returns list of dicts with id, name, data."""
        try:
            results = self.backend.find_by_prefix(prefix, limit=limit, raw=False)
            return [
                {
                    "id": r.get("id"),
                    "name": r.get("name") if isinstance(r.get("name"), str) else (r.get("name") or b"").decode("utf-8", errors="ignore"),
                    "data": r.get("data") if isinstance(r.get("data"), str) else (r.get("data") or b"").decode("utf-8", errors="ignore"),
                }
                for r in results
            ]
        except Exception:
            return []

    def count(self) -> int:
        """Approximate total node count (prefix '' with high limit)."""
        try:
            results = self.backend.find_by_prefix("", limit=50000)
            return len(results)
        except Exception:
            return 0

    def close(self):
        if self.backend:
            self.backend.close()


def get_ai_memory(lattice_path: Optional[str] = None, max_nodes: int = 100000) -> AIMemory:
    """Get an AIMemory instance (add/query/count API). Used by synrix.robotics and others."""
    return AIMemory(lattice_path=lattice_path, max_nodes=max_nodes)
