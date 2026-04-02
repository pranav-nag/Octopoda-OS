"""
Octopoda × AutoGen Integration
================================
Persistent memory for Microsoft AutoGen agents.
All memory is stored in the Octopoda Cloud API (api.octapodas.com).

Setup:
    pip install octopoda[client] pyautogen
    export OCTOPODA_API_KEY=sk-octopoda-...

Usage:
    from autogen import ConversableAgent
    from synrix.integrations.autogen import OctopodaAutoGenMemory

    memory = OctopodaAutoGenMemory(agent_id="autogen_assistant")

    assistant = ConversableAgent(
        name="assistant",
        system_message="You are a helpful assistant with persistent memory.",
        llm_config={"config_list": [{"model": "gpt-4"}]},
    )

    # Teach the agent something
    memory.remember("user_name", "Alice")
    memory.remember("project", "Building an AI startup")

    # Later, retrieve what it learned
    name = memory.recall("user_name")  # "Alice"

    # Search by meaning
    results = memory.search("startup details")

    # Use as a teachability replacement
    memory.learn_from_conversation(conversation_history)
"""

from __future__ import annotations

import time
import json
from typing import Any, Dict, List, Optional

from synrix.cloud import Octopoda

_client: Optional[Octopoda] = None


def _get_client() -> Octopoda:
    global _client
    if _client is None:
        _client = Octopoda()
    return _client


class OctopodaAutoGenMemory:
    """
    Persistent memory for AutoGen agents, backed by Octopoda Cloud.

    Replaces AutoGen's built-in Teachability with cloud-backed memory
    that includes semantic search, knowledge graphs, and temporal versioning.

    Requires OCTOPODA_API_KEY environment variable.
    Get your free key at https://octopodas.com
    """

    def __init__(
        self,
        agent_id: str = "autogen_agent",
        auto_learn: bool = True,
    ):
        self.agent_id = agent_id
        self.auto_learn = auto_learn
        client = _get_client()
        self._agent = client.agent(agent_id, metadata={"type": "autogen"})

    # ----- Core memory operations -----

    def remember(self, key: str, value: Any, tags: List[str] = None) -> bool:
        """Store a memory. Returns True on success."""
        try:
            self._agent.write(key, value, tags=tags)
            return True
        except Exception:
            return False

    def recall(self, key: str) -> Optional[Any]:
        """Recall a specific memory by key."""
        return self._agent.read(key)

    def search(self, query: str, limit: int = 5) -> List[Dict]:
        """Search memories by meaning (semantic search)."""
        return self._agent.search(query, limit=limit)

    def related(self, entity: str) -> Dict:
        """Query the knowledge graph for entity relationships."""
        relationships = self._agent.related(entity)
        return {
            "entity": entity,
            "relationships": relationships,
            "found": len(relationships) > 0,
        }

    def history(self, key: str) -> List[Dict]:
        """Get all versions of a memory over time."""
        return self._agent.history(key)

    # ----- AutoGen-specific: conversation learning -----

    def learn_from_conversation(self, messages: List[Dict]) -> int:
        """
        Extract and store knowledge from a conversation history.

        Args:
            messages: List of dicts with 'role' and 'content' keys
                      (standard AutoGen/OpenAI message format)

        Returns:
            Number of memories stored
        """
        stored = 0
        for i, msg in enumerate(messages):
            content = msg.get("content", "")
            role = msg.get("role", "user")
            name = msg.get("name", role)

            if not content or not isinstance(content, str):
                continue

            # Store each meaningful message
            key = f"conversation:turn_{i}:{name}"
            self.remember(key, content, tags=["conversation", name, role])
            stored += 1

        # Store conversation summary
        if messages:
            all_text = "\n".join(
                f"{m.get('name', m.get('role', 'unknown'))}: {m.get('content', '')}"
                for m in messages if m.get("content")
            )
            self.remember(
                f"conversation:summary:{int(time.time())}",
                all_text,
                tags=["conversation_summary"],
            )
            stored += 1

        return stored

    def get_relevant_context(self, query: str, limit: int = 3) -> str:
        """
        Get relevant context from memory for an agent's system message.

        Usage:
            context = memory.get_relevant_context("What do we know about the user?")
            system_message = f"You are a helpful assistant.\\n\\nRelevant context:\\n{context}"
        """
        results = self.search(query, limit=limit)
        if not results:
            return ""

        parts = []
        for r in results:
            val = r.get("value", "")
            score = r.get("score", 0)
            if score > 0.3:  # Only include reasonably relevant results
                parts.append(f"- {val}")

        return "\n".join(parts) if parts else ""

    # ----- AutoGen GroupChat support -----

    def save_group_message(self, sender: str, content: str, group_name: str = "default") -> bool:
        """Store a message from a group chat."""
        return self.remember(
            f"group:{group_name}:msg:{int(time.time() * 1000)}",
            {"sender": sender, "content": content, "timestamp": time.time()},
            tags=["group_chat", group_name, sender],
        )

    def get_group_history(self, group_name: str = "default", limit: int = 50) -> List[Dict]:
        """Get message history for a group chat."""
        return self._agent.keys(prefix=f"group:{group_name}:msg:", limit=limit)

    def search_group(self, query: str, group_name: str = "default", limit: int = 5) -> List[Dict]:
        """Search within a group chat's history."""
        all_results = self.search(query, limit=limit * 2)
        group_results = [
            r for r in all_results
            if f"group:{group_name}" in r.get("key", "")
        ]
        return group_results[:limit]
