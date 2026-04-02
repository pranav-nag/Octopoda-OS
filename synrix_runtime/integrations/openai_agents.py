"""
Octopoda × OpenAI Agents SDK Integration (Runtime)
====================================================
Persistent memory for OpenAI Agents SDK.
All memory is stored in the Octopoda Cloud API (api.octopodas.com).

Setup:
    pip install octopoda[client] openai-agents
    export OCTOPODA_API_KEY=sk-octopoda-...

Usage:
    from synrix_runtime.integrations.openai_agents import SynrixOpenAIMemory
    memory = SynrixOpenAIMemory()
    memory.store_thread_state("thread_123", {"messages": [...], "context": {...}})

For the full OpenAI Agents integration with tool wrappers, use:
    from synrix.integrations.openai_agents import octopoda_tools
"""

import time
import json
from typing import Dict, List, Optional, Any

from synrix.cloud import Octopoda

_client: Optional[Octopoda] = None


def _get_client() -> Octopoda:
    global _client
    if _client is None:
        _client = Octopoda()
    return _client


class SynrixOpenAIMemory:
    """Persistent memory for OpenAI Agents SDK, backed by Octopoda Cloud.

    Requires OCTOPODA_API_KEY environment variable.
    Get your free key at https://octopodas.com
    """

    def __init__(self):
        client = _get_client()
        self._agent = client.agent("openai_agents", metadata={"type": "openai_agents"})

    def store_thread_state(self, thread_id: str, state: dict):
        """Store the state of a thread."""
        payload = state.copy()
        payload["_stored_at"] = time.time()

        t0 = time.perf_counter()
        self._agent.write(
            f"openai:threads:{thread_id}:state",
            payload,
            tags=["openai_thread_state", thread_id],
        )
        latency_us = (time.perf_counter() - t0) * 1_000_000
        return {"thread_id": thread_id, "latency_us": round(latency_us, 1)}

    def restore_thread(self, thread_id: str) -> Optional[dict]:
        """Restore a thread's state."""
        t0 = time.perf_counter()
        value = self._agent.read(f"openai:threads:{thread_id}:state")
        latency_us = (time.perf_counter() - t0) * 1_000_000

        if value is not None:
            return {"state": value, "latency_us": round(latency_us, 1), "found": True}
        return {"state": None, "latency_us": round(latency_us, 1), "found": False}

    def store_run_result(self, run_id: str, result: dict):
        """Store the result of an agent run."""
        payload = result.copy() if isinstance(result, dict) else {"value": result}
        payload["_stored_at"] = time.time()

        t0 = time.perf_counter()
        self._agent.write(
            f"openai:runs:{run_id}",
            payload,
            tags=["openai_run_result", run_id],
        )
        latency_us = (time.perf_counter() - t0) * 1_000_000
        return {"run_id": run_id, "latency_us": round(latency_us, 1)}

    def get_agent_history(self, agent_name: str) -> list:
        """Get all runs for a specific agent."""
        results = self._agent.keys(prefix="openai:runs:", limit=200)
        history = []
        for r in results:
            val = r.get("value", r)
            if isinstance(val, dict) and val.get("agent_name") == agent_name:
                history.append(val)
        history.sort(key=lambda x: x.get("_stored_at", 0), reverse=True)
        return history

    def get_all_threads(self) -> list:
        """List all stored threads."""
        results = self._agent.keys(prefix="openai:threads:", limit=200)
        threads = []
        seen = set()
        for r in results:
            key = r.get("key", "")
            parts = key.split(":")
            if len(parts) >= 3:
                thread_id = parts[2]
                if thread_id not in seen:
                    seen.add(thread_id)
                    threads.append({"thread_id": thread_id, "state": r.get("value")})
        return threads

    def get_all_runs(self) -> list:
        """List all stored runs."""
        results = self._agent.keys(prefix="openai:runs:", limit=200)
        runs = []
        for r in results:
            val = r.get("value", r)
            runs.append(val)
        runs.sort(key=lambda x: x.get("_stored_at", 0) if isinstance(x, dict) else 0, reverse=True)
        return runs
