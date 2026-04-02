"""
Octopoda × AutoGen Integration (Runtime)
==========================================
Persistent conversation history for AutoGen agents.
All memory is stored in the Octopoda Cloud API (api.octopodas.com).

Setup:
    pip install octopoda[client] pyautogen
    export OCTOPODA_API_KEY=sk-octopoda-...

Usage:
    from synrix_runtime.integrations.autogen_memory import SynrixAutoGenMemory
    memory = SynrixAutoGenMemory(group_id="my_autogen_group")

For the full AutoGen integration, use:
    from synrix.integrations.autogen import OctopodaAutoGenMemory
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


class SynrixAutoGenMemory:
    """Persistent conversation history for AutoGen agents, backed by Octopoda Cloud.

    Requires OCTOPODA_API_KEY environment variable.
    Get your free key at https://octopodas.com
    """

    def __init__(self, group_id: str = "default"):
        self.group_id = group_id
        client = _get_client()
        self._agent = client.agent(f"autogen_{group_id}", metadata={"type": "autogen", "group": group_id})

    def store_message(self, sender: str, recipient: str, content: str, timestamp: float = None):
        """Store a message in the conversation history."""
        if timestamp is None:
            timestamp = time.time()
        ts = int(timestamp * 1000000)

        entry = {
            "sender": sender,
            "recipient": recipient,
            "content": content,
            "timestamp": timestamp,
        }

        t0 = time.perf_counter()
        self._agent.write(
            f"autogen:{self.group_id}:messages:{sender}:{recipient}:{ts}",
            entry,
            tags=["autogen_message", sender, recipient],
        )
        latency_us = (time.perf_counter() - t0) * 1_000_000
        return {"latency_us": round(latency_us, 1)}

    def get_conversation_history(self, agent_pair: tuple = None, limit: int = 100) -> list:
        """Get conversation history, optionally between a specific pair."""
        if agent_pair:
            sender, recipient = agent_pair
            prefix = f"autogen:{self.group_id}:messages:{sender}:{recipient}:"
        else:
            prefix = f"autogen:{self.group_id}:messages:"

        results = self._agent.keys(prefix=prefix, limit=limit)
        messages = []
        for r in results:
            val = r.get("value", r)
            if isinstance(val, dict):
                messages.append(val)
        messages.sort(key=lambda x: x.get("timestamp", 0))
        return messages

    def search_conversations(self, query_text: str) -> list:
        """Search through all conversations using semantic search."""
        return self._agent.search(query_text, limit=20)

    def get_agent_knowledge(self, agent_name: str) -> list:
        """Get all messages sent by a specific agent."""
        results = self._agent.keys(prefix=f"autogen:{self.group_id}:messages:{agent_name}:", limit=200)
        messages = []
        for r in results:
            val = r.get("value", r)
            if isinstance(val, dict):
                messages.append(val)
        messages.sort(key=lambda x: x.get("timestamp", 0))
        return messages

    def export_conversation(self, agent_pair: tuple = None, format: str = "json") -> str:
        """Export conversation history."""
        messages = self.get_conversation_history(agent_pair)
        if format == "json":
            return json.dumps({"group_id": self.group_id, "messages": messages, "exported_at": time.time()}, indent=2)
        else:
            lines = []
            for msg in messages:
                lines.append(f"[{msg.get('sender')} -> {msg.get('recipient')}] {msg.get('content')}")
            return "\n".join(lines)

    def get_stats(self) -> dict:
        """Get conversation statistics."""
        messages = self.get_conversation_history(limit=500)
        agents = set()
        for msg in messages:
            agents.add(msg.get("sender", ""))
            agents.add(msg.get("recipient", ""))
        agents.discard("")

        return {
            "group_id": self.group_id,
            "total_messages": len(messages),
            "unique_agents": len(agents),
            "agents": list(agents),
        }
