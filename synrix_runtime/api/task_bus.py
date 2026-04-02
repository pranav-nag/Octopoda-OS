"""
Synrix Agent Runtime — Task Bus
Task handoff, claiming, and completion tracking.
"""

import time
from typing import Dict, List, Optional, Any


class TaskBus:
    """Manages task lifecycle: handoff, claim, complete."""

    def __init__(self, backend=None):
        self.backend = backend
        if self.backend is None:
            from synrix.agent_backend import get_synrix_backend
            from synrix_runtime.config import SynrixConfig
            config = SynrixConfig.from_env()
            self.backend = get_synrix_backend(**config.get_backend_kwargs())

    def create_task(self, task_id: str, from_agent: str, to_agent: str, payload: dict) -> dict:
        """Create a task handoff."""
        task = {
            "task_id": task_id,
            "from_agent": from_agent,
            "to_agent": to_agent,
            "payload": payload,
            "status": "pending",
            "created_at": time.time(),
        }

        start = time.perf_counter_ns()
        node_id = self.backend.write(f"tasks:handoff:{task_id}", task, metadata={"type": "task_handoff"})
        latency_us = (time.perf_counter_ns() - start) / 1000

        return {"task_id": task_id, "node_id": node_id, "latency_us": latency_us}

    def claim_task(self, task_id: str, agent_id: str) -> Optional[dict]:
        """Claim a pending task."""
        result = self.backend.read(f"tasks:handoff:{task_id}")
        if result is None:
            return None

        data = result.get("data", {})
        val = data.get("value", data)
        if isinstance(val, dict):
            val["status"] = "claimed"
            val["claimed_by"] = agent_id
            val["claimed_at"] = time.time()
        self.backend.write(f"tasks:handoff:{task_id}", val, metadata={"type": "task_claimed"})
        return val

    def complete_task(self, task_id: str, agent_id: str, result: dict) -> dict:
        """Mark a task as complete."""
        completion = {
            "task_id": task_id,
            "completed_by": agent_id,
            "result": result,
            "status": "completed",
            "completed_at": time.time(),
        }

        start = time.perf_counter_ns()
        self.backend.write(f"tasks:complete:{task_id}", completion, metadata={"type": "task_complete"})
        latency_us = (time.perf_counter_ns() - start) / 1000

        return {"task_id": task_id, "latency_us": latency_us}

    def get_task(self, task_id: str) -> Optional[dict]:
        """Get a task by ID."""
        result = self.backend.read(f"tasks:handoff:{task_id}")
        if result:
            data = result.get("data", {})
            return data.get("value", data)
        return None

    def get_pending_tasks(self, agent_id: str = None) -> list:
        """Get all pending tasks, optionally filtered by target agent."""
        results = self.backend.query_prefix("tasks:handoff:", limit=200)
        tasks = []
        for r in results:
            data = r.get("data", {})
            val = data.get("value", data)
            if isinstance(val, dict) and val.get("status") == "pending":
                if agent_id is None or val.get("to_agent") == agent_id:
                    tasks.append(val)
        return tasks

    def get_completed_tasks(self, limit: int = 50) -> list:
        """Get completed tasks."""
        results = self.backend.query_prefix("tasks:complete:", limit=limit)
        tasks = []
        for r in results:
            data = r.get("data", {})
            val = data.get("value", data)
            tasks.append(val)
        tasks.sort(key=lambda x: x.get("completed_at", 0) if isinstance(x, dict) else 0, reverse=True)
        return tasks

    def get_all_tasks(self) -> list:
        """Get all tasks (pending + completed)."""
        handoffs = self.backend.query_prefix("tasks:handoff:", limit=200)
        completions = self.backend.query_prefix("tasks:complete:", limit=200)

        tasks = []
        for r in handoffs + completions:
            data = r.get("data", {})
            val = data.get("value", data)
            tasks.append(val)
        return tasks
