"""
Octopoda -- Persistent Memory Kernel for AI Agents
====================================================
Install: pip install octopoda

Quick start:
    from octopoda import AgentRuntime
    agent = AgentRuntime("my_agent")
    agent.remember("key", {"data": "value"})
    result = agent.recall("key")
"""

__version__ = "3.0.3"

# Cloud SDK (the main developer-facing API)
from synrix.cloud import Octopoda, Agent, OctopodaError, AuthError, RateLimitError

# Core SDK (low-level)
from synrix import (
    SynrixAgentBackend,
    get_synrix_backend,
    SynrixError,
    SynrixConnectionError,
    SynrixNotFoundError,
)

try:
    from synrix import Memory
except ImportError:
    Memory = None

# Runtime (high-level developer API)
from synrix_runtime.api.runtime import AgentRuntime
from synrix_runtime.config import SynrixConfig

# Framework integrations (lazy imports to avoid requiring all dependencies)
def _lazy_langchain():
    from synrix_runtime.integrations.langchain_memory import SynrixMemory
    return SynrixMemory

def _lazy_crewai():
    from synrix_runtime.integrations.crewai_memory import SynrixCrewMemory
    return SynrixCrewMemory

def _lazy_autogen():
    from synrix_runtime.integrations.autogen_memory import SynrixAutoGenMemory
    return SynrixAutoGenMemory

def _lazy_openai():
    from synrix_runtime.integrations.openai_agents import SynrixOpenAIMemory
    return SynrixOpenAIMemory


__all__ = [
    "Octopoda",
    "Agent",
    "OctopodaError",
    "AuthError",
    "RateLimitError",
    "AgentRuntime",
    "SynrixConfig",
    "get_synrix_backend",
    "SynrixAgentBackend",
    "Memory",
    "SynrixError",
    "SynrixConnectionError",
    "SynrixNotFoundError",
]
