"""
Octopoda × OpenAI Agents SDK Integration
==========================================
Persistent memory tools for OpenAI Agents.
All memory is stored in the Octopoda Cloud API (api.octapodas.com).

Setup:
    pip install octopoda[client] openai-agents
    export OCTOPODA_API_KEY=sk-octopoda-...

Usage:
    from agents import Agent, Runner
    from synrix.integrations.openai_agents import octopoda_tools

    agent = Agent(
        name="Support Bot",
        instructions="You are a helpful support agent. Use your memory tools.",
        tools=octopoda_tools("support_bot"),
    )

    # The agent can now:
    #   - remember(key, value)     → store a memory
    #   - recall(key)              → retrieve a memory
    #   - search(query)            → semantic search
    #   - related(entity)          → knowledge graph query
    #   - history(key)             → view memory versions

    result = Runner.run_sync(agent, "My name is Alice and I prefer dark mode")
    # Agent auto-stores: name=Alice, preference=dark_mode

    result = Runner.run_sync(agent, "What's my name?")
    # Agent recalls: Alice
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from synrix.cloud import Octopoda, Agent as OctopodaAgent

# Shared client singleton
_client: Optional[Octopoda] = None
_agents: Dict[str, OctopodaAgent] = {}


def _get_client() -> Octopoda:
    global _client
    if _client is None:
        _client = Octopoda()
    return _client


def _get_agent(agent_id: str) -> OctopodaAgent:
    if agent_id not in _agents:
        client = _get_client()
        _agents[agent_id] = client.agent(agent_id, metadata={"type": "openai_agents"})
    return _agents[agent_id]


# ---------------------------------------------------------------------------
# Tool functions (standalone — work with or without the openai-agents SDK)
# ---------------------------------------------------------------------------

def remember(agent_id: str, key: str, value: str) -> str:
    """Store a memory that persists across conversations."""
    agent = _get_agent(agent_id)
    try:
        agent.write(key, value)
        return json.dumps({"stored": True, "key": key})
    except Exception as e:
        return json.dumps({"stored": False, "error": str(e)})


def recall(agent_id: str, key: str) -> str:
    """Retrieve a specific memory by key."""
    agent = _get_agent(agent_id)
    value = agent.read(key)
    if value is not None:
        return json.dumps({"found": True, "key": key, "value": value})
    return json.dumps({"found": False, "key": key})


def search_memory(agent_id: str, query: str, limit: int = 5) -> str:
    """Search memories by meaning. Returns the most relevant matches."""
    agent = _get_agent(agent_id)
    results = agent.search(query, limit=limit)
    return json.dumps({
        "query": query,
        "results": results,
        "count": len(results),
    })


def related_entities(agent_id: str, entity: str) -> str:
    """Find what's connected to an entity in the knowledge graph."""
    agent = _get_agent(agent_id)
    relationships = agent.related(entity)
    return json.dumps({
        "entity": entity,
        "relationships": relationships,
        "found": len(relationships) > 0,
    })


def memory_history(agent_id: str, key: str) -> str:
    """Get all versions of a memory over time."""
    agent = _get_agent(agent_id)
    versions = agent.history(key)
    return json.dumps({
        "key": key,
        "versions": versions,
    })


# ---------------------------------------------------------------------------
# OpenAI Agents SDK tool wrappers
# ---------------------------------------------------------------------------

def octopoda_tools(agent_id: str) -> list:
    """
    Returns a list of OpenAI Agents SDK tool definitions for Octopoda memory.

    Usage:
        from agents import Agent
        from synrix.integrations.openai_agents import octopoda_tools

        agent = Agent(
            name="My Agent",
            tools=octopoda_tools("my_agent"),
        )
    """
    try:
        from agents import function_tool
    except ImportError:
        # If openai-agents not installed, return plain tool definitions
        return _plain_tool_definitions(agent_id)

    # Create closures that bind agent_id
    @function_tool
    def remember_memory(key: str, value: str) -> str:
        """Store a memory that persists across conversations. Use this to save user preferences, facts, decisions, or any important information."""
        return remember(agent_id, key, value)

    @function_tool
    def recall_memory(key: str) -> str:
        """Retrieve a specific memory by its key. Use this when you need to look up a previously stored piece of information."""
        return recall(agent_id, key)

    @function_tool
    def search_memories(query: str) -> str:
        """Search all memories by meaning. Use this to find relevant information when you don't know the exact key. Returns the most semantically similar matches."""
        return search_memory(agent_id, query)

    @function_tool
    def find_related(entity: str) -> str:
        """Find entities related to a given entity in the knowledge graph. Use this to discover connections between people, places, concepts, etc."""
        return related_entities(agent_id, entity)

    @function_tool
    def get_history(key: str) -> str:
        """Get all historical versions of a memory. Use this to see how a piece of information has changed over time."""
        return memory_history(agent_id, key)

    return [remember_memory, recall_memory, search_memories, find_related, get_history]


def _plain_tool_definitions(agent_id: str) -> list:
    """Fallback tool definitions as plain dicts (for use without openai-agents SDK)."""
    return [
        {
            "type": "function",
            "function": {
                "name": "remember_memory",
                "description": "Store a memory that persists across conversations.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "Memory key (e.g., 'user_name', 'preference')"},
                        "value": {"type": "string", "description": "The value to remember"},
                    },
                    "required": ["key", "value"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "recall_memory",
                "description": "Retrieve a specific memory by its key.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "Memory key to recall"},
                    },
                    "required": ["key"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_memories",
                "description": "Search all memories by meaning. Returns semantically similar matches.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Natural language search query"},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "find_related",
                "description": "Find entities related to a given entity in the knowledge graph.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entity": {"type": "string", "description": "Entity name to look up"},
                    },
                    "required": ["entity"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_history",
                "description": "Get all historical versions of a memory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "Memory key to get history for"},
                    },
                    "required": ["key"],
                },
            },
        },
    ]


# ---------------------------------------------------------------------------
# OpenAI function calling handler (for raw OpenAI API usage)
# ---------------------------------------------------------------------------

def handle_tool_call(agent_id: str, function_name: str, arguments: dict) -> str:
    """
    Handle an OpenAI function call response.

    Usage with raw OpenAI API:
        from synrix.integrations.openai_agents import handle_tool_call

        # In your tool-call handling loop:
        for tool_call in response.choices[0].message.tool_calls:
            result = handle_tool_call(
                "my_agent",
                tool_call.function.name,
                json.loads(tool_call.function.arguments),
            )
    """
    handlers = {
        "remember_memory": lambda a: remember(agent_id, a["key"], a["value"]),
        "recall_memory": lambda a: recall(agent_id, a["key"]),
        "search_memories": lambda a: search_memory(agent_id, a.get("query", "")),
        "find_related": lambda a: related_entities(agent_id, a.get("entity", "")),
        "get_history": lambda a: memory_history(agent_id, a.get("key", "")),
    }
    handler = handlers.get(function_name)
    if handler:
        return handler(arguments)
    return json.dumps({"error": f"Unknown function: {function_name}"})
