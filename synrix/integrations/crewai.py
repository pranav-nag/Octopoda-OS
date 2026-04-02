"""
Octopoda × CrewAI Integration
===============================
Persistent memory for CrewAI crews and agents.
All memory is stored in the Octopoda Cloud API (api.octapodas.com).

Setup:
    pip install octopoda[client] crewai
    export OCTOPODA_API_KEY=sk-octopoda-...

Usage:
    from crewai import Agent, Task, Crew
    from synrix.integrations.crewai import OctopodaCrewMemory

    memory = OctopodaCrewMemory(agent_id="research_crew")

    researcher = Agent(
        role="Researcher",
        goal="Find information",
        backstory="Expert researcher",
    )

    task = Task(
        description="Research quantum computing",
        agent=researcher,
    )

    crew = Crew(
        agents=[researcher],
        tasks=[task],
        memory=True,  # Enable CrewAI memory
    )

    # Use Octopoda for persistent memory across crew runs:
    memory.save_crew_result("quantum_research", crew.kickoff())
    previous = memory.recall("quantum_research")

    # Search across all crew knowledge:
    results = memory.search("quantum computing breakthroughs")
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


class OctopodaCrewMemory:
    """
    Persistent memory layer for CrewAI, backed by Octopoda Cloud.

    Stores crew task results, agent interactions, and shared knowledge
    in the cloud. Memories persist across crew runs and are searchable
    by meaning (semantic search).

    Requires OCTOPODA_API_KEY environment variable.
    Get your free key at https://octopodas.com
    """

    def __init__(
        self,
        agent_id: str = "crewai_agent",
        crew_name: str = "default_crew",
    ):
        self.agent_id = agent_id
        self.crew_name = crew_name
        client = _get_client()
        self._agent = client.agent(agent_id, metadata={"type": "crewai", "crew": crew_name})

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

    def search(self, query: str, limit: int = 10) -> List[Dict]:
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

    # ----- CrewAI-specific operations -----

    def save_crew_result(self, task_name: str, result: Any) -> bool:
        """Save a crew task result to memory."""
        value = str(result) if not isinstance(result, (dict, str)) else result
        return self.remember(
            f"crew:{self.crew_name}:task:{task_name}",
            value,
            tags=["crew_result", self.crew_name, task_name],
        )

    def get_crew_result(self, task_name: str) -> Optional[Any]:
        """Retrieve a previous crew task result."""
        return self.recall(f"crew:{self.crew_name}:task:{task_name}")

    def save_agent_output(self, agent_role: str, task_name: str, output: Any) -> bool:
        """Save an individual agent's output from a task."""
        value = str(output) if not isinstance(output, (dict, str)) else output
        return self.remember(
            f"crew:{self.crew_name}:agent:{agent_role}:{task_name}",
            value,
            tags=["agent_output", agent_role, task_name],
        )

    def get_agent_outputs(self, agent_role: str) -> List[Dict]:
        """Get all outputs from a specific agent."""
        return self._agent.keys(prefix=f"crew:{self.crew_name}:agent:{agent_role}:")

    def save_shared_knowledge(self, key: str, value: Any) -> bool:
        """Store knowledge shared across all crew agents."""
        return self.remember(
            f"crew:{self.crew_name}:shared:{key}",
            value,
            tags=["shared_knowledge", self.crew_name],
        )

    def get_shared_knowledge(self, key: str) -> Optional[Any]:
        """Retrieve shared knowledge."""
        return self.recall(f"crew:{self.crew_name}:shared:{key}")

    def get_crew_summary(self) -> Dict:
        """Get a summary of all crew activity."""
        tasks = self._agent.keys(prefix=f"crew:{self.crew_name}:task:")
        agents = self._agent.keys(prefix=f"crew:{self.crew_name}:agent:")
        shared = self._agent.keys(prefix=f"crew:{self.crew_name}:shared:")
        return {
            "crew_name": self.crew_name,
            "task_results": len(tasks),
            "agent_outputs": len(agents),
            "shared_knowledge": len(shared),
            "total_memories": len(tasks) + len(agents) + len(shared),
        }

    # ----- CrewAI callback hooks -----

    def on_task_start(self, task_name: str, agent_role: str) -> None:
        """Hook: called when a task begins (for tracking)."""
        self.remember(
            f"crew:{self.crew_name}:events:task_start:{task_name}",
            {
                "event": "task_start",
                "task": task_name,
                "agent": agent_role,
                "timestamp": time.time(),
            },
        )

    def on_task_complete(self, task_name: str, agent_role: str, output: Any) -> None:
        """Hook: called when a task completes."""
        self.save_agent_output(agent_role, task_name, output)
        self.save_crew_result(task_name, output)

    def on_crew_complete(self, final_output: Any) -> None:
        """Hook: called when the entire crew finishes."""
        self.remember(
            f"crew:{self.crew_name}:final_output",
            str(final_output) if not isinstance(final_output, (dict, str)) else final_output,
            tags=["final_output", self.crew_name],
        )
