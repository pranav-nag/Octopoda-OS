"""
Octopoda × LangChain Integration (Runtime)
============================================
Drop-in replacement for LangChain memory modules.
All memory is stored in the Octopoda Cloud API (api.octopodas.com).

Setup:
    pip install octopoda[client] langchain
    export OCTOPODA_API_KEY=sk-octopoda-...

Usage:
    from synrix_runtime.integrations.langchain_memory import SynrixMemory
    memory = SynrixMemory(agent_id="my_chain")
    chain = ConversationChain(llm=llm, memory=memory)

For the full LangChain integration (BaseMemory, ChatMessageHistory), use:
    from synrix.integrations.langchain import OctopodaMemory, OctopodaChatHistory
"""

import time
import json
from typing import Dict, List, Any, Optional

from synrix.cloud import Octopoda

try:
    from langchain.memory import BaseMemory
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    class BaseMemory:
        """Stub when LangChain not installed."""
        memory_variables = []
        def save_context(self, inputs, outputs): pass
        def load_memory_variables(self, inputs): return {}
        def clear(self): pass


_client: Optional[Octopoda] = None


def _get_client() -> Octopoda:
    global _client
    if _client is None:
        _client = Octopoda()
    return _client


class SynrixMemory(BaseMemory):
    """
    Drop-in replacement for LangChain memory backed by Octopoda Cloud.

    Usage:
        from synrix_runtime.integrations.langchain_memory import SynrixMemory
        memory = SynrixMemory(agent_id="my_chain")
        # Use with LangChain: ConversationChain(llm=llm, memory=memory)

    Requires OCTOPODA_API_KEY environment variable.
    Get your free key at https://octopodas.com
    """

    def __init__(self, agent_id: str = "langchain_default", memory_key: str = "history", **kwargs):
        self.agent_id = agent_id
        self.memory_key = memory_key
        self._memory_variables = [memory_key]
        self._message_count = 0

        client = _get_client()
        self._agent = client.agent(agent_id, metadata={"type": "langchain"})

    @property
    def memory_variables(self) -> List[str]:
        return self._memory_variables

    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, str]) -> None:
        """Save conversation turn to Octopoda Cloud."""
        self._message_count += 1

        entry = {
            "inputs": inputs,
            "outputs": outputs,
            "turn": self._message_count,
            "timestamp": time.time(),
        }

        self._agent.write(
            f"langchain:{self.agent_id}:messages:{int(time.time() * 1000000)}",
            entry,
            tags=["langchain_message", self.agent_id],
        )

        # Update summary
        self._agent.write(
            f"langchain:{self.agent_id}:summary",
            {"total_turns": self._message_count, "last_updated": time.time()},
        )

    def load_memory_variables(self, inputs: Dict[str, Any] = None) -> Dict[str, Any]:
        """Load conversation history from Octopoda Cloud."""
        results = self._agent.keys(prefix=f"langchain:{self.agent_id}:messages:", limit=100)

        messages = []
        for r in results:
            val = r.get("value", r)
            if isinstance(val, dict):
                messages.append(val)

        messages.sort(key=lambda x: x.get("turn", 0))

        history_parts = []
        for msg in messages:
            inp = msg.get("inputs", {})
            out = msg.get("outputs", {})
            human_input = inp.get("input", inp.get("human_input", str(inp)))
            ai_output = out.get("output", out.get("response", str(out)))
            history_parts.append(f"Human: {human_input}")
            history_parts.append(f"AI: {ai_output}")

        return {self.memory_key: "\n".join(history_parts)}

    def clear(self) -> None:
        """Clear is a no-op — Octopoda preserves all history."""
        pass

    def get_full_history(self) -> List[dict]:
        """Get complete conversation history."""
        results = self._agent.keys(prefix=f"langchain:{self.agent_id}:messages:", limit=500)
        messages = []
        for r in results:
            val = r.get("value", r)
            if isinstance(val, dict):
                messages.append(val)
        messages.sort(key=lambda x: x.get("turn", 0))
        return messages

    def export_conversation(self) -> dict:
        """Export full conversation with metadata."""
        messages = self.get_full_history()
        return {
            "agent_id": self.agent_id,
            "total_turns": len(messages),
            "messages": messages,
            "exported_at": time.time(),
        }
