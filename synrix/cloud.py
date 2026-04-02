"""
Octopoda Cloud SDK
==================
Python client for the Octopoda Agent Memory API.

    from synrix import Octopoda

    client = Octopoda(api_key="sk-octopoda-...", base_url="https://api.octapodas.com")
    agent = client.agent("my-bot")
    agent.write("user:alice", {"name": "Alice", "score": 95})
    data = agent.read("user:alice")
"""

import os
import requests
import time
from typing import Any, Dict, List, Optional


class OctopodaError(Exception):
    """Base exception for Octopoda SDK."""
    pass


class AuthError(OctopodaError):
    """Authentication failed."""
    pass


class RateLimitError(OctopodaError):
    """Rate limit exceeded."""
    def __init__(self, msg, retry_after=1):
        super().__init__(msg)
        self.retry_after = retry_after


class Agent:
    """Handle for a single agent — all memory, audit, and recovery ops."""

    def __init__(self, client: "Octopoda", agent_id: str):
        self._client = client
        self.agent_id = agent_id

    # -- Memory -----------------------------------------------------------

    def write(self, key: str, value: Any, metadata: Optional[Dict] = None, tags: Optional[List[str]] = None) -> Dict:
        """Store a memory.

        Args:
            key: Memory key (e.g. "customer:alice")
            value: Any JSON-serialisable value
            metadata: Optional metadata dict
            tags: Optional list of tags for filtering
        """
        body: Dict[str, Any] = {"key": key, "value": value}
        if metadata:
            body["metadata"] = metadata
        if tags:
            body["tags"] = tags
        return self._client._post(f"/v1/agents/{self.agent_id}/remember", body)

    def write_batch(self, items: List[Dict[str, Any]]) -> Dict:
        """Store multiple memories at once.

        Args:
            items: List of dicts with "key", "value", and optional "metadata"/"tags"
        """
        return self._client._post(f"/v1/agents/{self.agent_id}/remember/batch", {"items": items})

    def read(self, key: str) -> Optional[Any]:
        """Recall a single memory by key."""
        resp = self._client._get(f"/v1/agents/{self.agent_id}/recall/{key}")
        if resp.get("found"):
            return resp.get("value")
        return None

    def list(self, limit: int = 50, offset: int = 0) -> Dict:
        """List all memories for this agent."""
        return self._client._get(f"/v1/agents/{self.agent_id}/memory", params={"limit": limit, "offset": offset})

    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """Semantic search — find memories by meaning, not exact keys.

        Args:
            query: Natural language query (e.g. "enterprise customers")
            limit: Max results to return (default 10)

        Returns:
            List of dicts with key, value, score (0-1, higher = better match)
        """
        resp = self._client._get(f"/v1/agents/{self.agent_id}/similar", params={"q": query, "limit": limit})
        return resp.get("items", [])

    def keys(self, prefix: str = "", limit: int = 50) -> List[Dict]:
        """Search memories by key prefix.

        Args:
            prefix: Key prefix to filter by (e.g. "customer:" returns all customer keys)
            limit: Max results to return (default 50)
        """
        resp = self._client._get(f"/v1/agents/{self.agent_id}/search", params={"prefix": prefix, "limit": limit})
        return resp.get("items", [])

    def history(self, key: str) -> List[Dict]:
        """Get version history for a memory key."""
        resp = self._client._get(f"/v1/agents/{self.agent_id}/history/{key}")
        return resp.get("versions", [])

    def related(self, entity: str) -> List[Dict]:
        """Get knowledge graph relationships for an entity."""
        resp = self._client._get(f"/v1/agents/{self.agent_id}/related/{entity}")
        return resp.get("relationships", [])

    # -- TTL / Auto-Expire ------------------------------------------------

    def write_ttl(self, key: str, value: Any, ttl_seconds: int = 3600,
                  tags: Optional[List[str]] = None) -> Dict:
        """Store a memory that auto-expires after ttl_seconds.

        Args:
            key: Memory key
            value: Any JSON-serialisable value
            ttl_seconds: Time to live in seconds (default 1 hour, max 1 year)
            tags: Optional tags
        """
        body = {"key": key, "value": value, "ttl_seconds": ttl_seconds}
        if tags:
            body["tags"] = tags
        return self._client._post(f"/v1/agents/{self.agent_id}/remember/ttl", body)

    def cleanup_expired(self) -> Dict:
        """Remove all expired TTL memories for this agent."""
        return self._client._post(f"/v1/agents/{self.agent_id}/cleanup")

    # -- Importance Scoring -----------------------------------------------

    def write_important(self, key: str, value: Any, importance: str = "normal",
                        tags: Optional[List[str]] = None) -> Dict:
        """Store a memory with importance level.

        Args:
            key: Memory key
            value: Any JSON-serialisable value
            importance: "critical", "normal", or "low"
            tags: Optional tags
        """
        body = {"key": key, "value": value, "importance": importance}
        if tags:
            body["tags"] = tags
        return self._client._post(f"/v1/agents/{self.agent_id}/remember/important", body)

    # -- Conflict Detection -----------------------------------------------

    def check_conflicts(self, key: str, value: Any, threshold: float = 0.7) -> Dict:
        """Check if a value conflicts with existing memories.

        Args:
            key: The key being written
            value: The value to check for contradictions
            threshold: Similarity threshold (0-1) to flag as conflict

        Returns:
            Dict with 'has_conflicts' bool and 'conflicts' list
        """
        return self._client._post(f"/v1/agents/{self.agent_id}/conflicts", {
            "key": key, "value": value, "threshold": threshold,
        })

    def write_safe(self, key: str, value: Any, tags: Optional[List[str]] = None,
                   conflict_threshold: float = 0.85) -> Dict:
        """Write a memory and return any detected conflicts.

        Args:
            key: Memory key
            value: Value to store
            tags: Optional tags
            conflict_threshold: Similarity threshold to flag conflicts

        Returns:
            Dict with 'write' result and 'conflicts' info
        """
        body = {"key": key, "value": value, "conflict_threshold": conflict_threshold}
        if tags:
            body["tags"] = tags
        return self._client._post(f"/v1/agents/{self.agent_id}/remember/safe", body)

    # -- Enrichment Control --------------------------------------------------

    def flush(self, timeout: float = 60.0) -> Dict:
        """Wait for all pending background enrichment to complete.

        Call after writes to ensure memories are searchable via semantic search.
        Blocks until embeddings, facts, and NER are done (or timeout).

        Returns:
            Dict with counts: pending, completed, failed, timed_out
        """
        return self._client._post(f"/v1/agents/{self.agent_id}/flush", {})

    # -- Conversation Processing (high-level API) -------------------------

    def process_conversation(self, messages: List[Dict[str, str]],
                              extract_preferences: bool = True,
                              extract_facts: bool = True,
                              extract_decisions: bool = True,
                              namespace: str = "conversations") -> Dict:
        """Process a conversation and auto-extract memories.

        This is the easiest way to add memory to your agent.
        Just pass the conversation messages and Octopoda extracts
        preferences, facts, and decisions automatically.

        Args:
            messages: List of {"role": "user"|"assistant", "content": "..."}
            extract_preferences: Extract user preferences (default True)
            extract_facts: Extract factual statements (default True)
            extract_decisions: Extract decisions/actions (default True)
            namespace: Key prefix for stored memories (default "conversations")

        Returns:
            Dict with memories_stored count and details

        Example:
            agent.process_conversation([
                {"role": "user", "content": "I prefer dark mode and bullet points"},
                {"role": "assistant", "content": "Got it! I'll use dark mode."},
            ])
        """
        return self._client._post(f"/v1/agents/{self.agent_id}/process-conversation", {
            "messages": messages,
            "extract_preferences": extract_preferences,
            "extract_facts": extract_facts,
            "extract_decisions": extract_decisions,
            "namespace": namespace,
        })

    def get_context(self, query: str, limit: int = 10, format: str = "text") -> Any:
        """Get relevant context from memory for a query.

        Call this before your agent generates a response to give it
        access to everything it has learned about the user/topic.

        Args:
            query: The current user message or topic
            limit: Max memories to retrieve (default 10)
            format: "text" for LLM-ready string, "raw" for list of dicts

        Returns:
            If format="text": Dict with 'context' string ready to inject into prompts
            If format="raw": Dict with 'memories' list of matching memory objects

        Example:
            ctx = agent.get_context("Help me write a report")
            # ctx["context"] = "User prefers bullet points\\n---\\nUser likes dark mode"
        """
        return self._client._post(f"/v1/agents/{self.agent_id}/context", {
            "query": query,
            "limit": limit,
            "format": format,
        })

    # -- Usage Analytics --------------------------------------------------

    def analytics(self) -> Dict:
        """Get detailed usage analytics for this agent."""
        return self._client._get(f"/v1/agents/{self.agent_id}/analytics")

    # -- Audit ------------------------------------------------------------

    def decide(self, decision: str, reasoning: str, context: Optional[Dict] = None) -> Dict:
        """Log an audit decision.

        Args:
            decision: "allow", "deny", or "escalate"
            reasoning: Human-readable explanation
            context: Optional context dict (resource, action, etc.)
        """
        body = {"decision": decision, "reasoning": reasoning}
        if context:
            body["context"] = context
        return self._client._post(f"/v1/agents/{self.agent_id}/decision", body)

    def audit(self, limit: int = 50) -> List[Dict]:
        """Get audit trail for this agent."""
        resp = self._client._get(f"/v1/agents/{self.agent_id}/audit", params={"limit": limit})
        return resp.get("events", [])

    # -- Recovery ---------------------------------------------------------

    def recover(self) -> Dict:
        """Trigger crash recovery for this agent."""
        return self._client._post(f"/v1/agents/{self.agent_id}/recover")

    # -- Shared Memory ----------------------------------------------------

    def share(self, space: str, key: str, value: Any) -> Dict:
        """Write to a shared memory space.

        Args:
            space: Space name (e.g. "team-config", "incident-log")
            key: Key within the space
            value: Any JSON-serialisable value
        """
        return self._client._post(f"/v1/shared/{space}", {
            "key": key,
            "value": value,
            "author_agent_id": self.agent_id,
        })

    # -- Snapshots --------------------------------------------------------

    def snapshot(self, label: Optional[str] = None) -> Dict:
        """Take a snapshot of agent state."""
        body = {}
        if label:
            body["label"] = label
        return self._client._post(f"/v1/agents/{self.agent_id}/snapshot", body)

    def restore(self, snapshot_id: str) -> Dict:
        """Restore agent from a snapshot."""
        return self._client._post(f"/v1/agents/{self.agent_id}/restore", {"snapshot_id": snapshot_id})

    # -- Metrics ----------------------------------------------------------

    def metrics(self) -> Dict:
        """Get performance metrics for this agent."""
        return self._client._get(f"/v1/agents/{self.agent_id}/metrics")

    # -- Info -------------------------------------------------------------

    def info(self) -> Dict:
        """Get agent details (state, metadata, metrics)."""
        return self._client._get(f"/v1/agents/{self.agent_id}")

    def delete(self) -> Dict:
        """Deregister this agent."""
        return self._client._delete(f"/v1/agents/{self.agent_id}")

    # -- Memory Management (Forget / Consolidate / Health) ------------------

    def forget(self, key: str) -> Dict:
        """Explicitly forget (delete) a specific memory.

        Args:
            key: The memory key to forget
        """
        return self._client._delete(f"/v1/agents/{self.agent_id}/memory/{key}")

    def forget_stale(self, max_age_seconds: int = 604800) -> Dict:
        """Forget memories older than max_age_seconds (default 7 days).

        Critical memories are preserved regardless of age.
        """
        return self._client._post(f"/v1/agents/{self.agent_id}/forget/stale", {
            "max_age_seconds": max_age_seconds,
        })

    def forget_by_tag(self, tag: str) -> Dict:
        """Forget all memories with a specific tag.

        Args:
            tag: Tag to match for deletion
        """
        return self._client._post(f"/v1/agents/{self.agent_id}/forget/tag", {"tag": tag})

    def consolidate(self, similarity_threshold: float = 0.90, dry_run: bool = True) -> Dict:
        """Find and optionally merge duplicate memories.

        Args:
            similarity_threshold: How similar memories must be to count as duplicates (0-1)
            dry_run: If True (default), reports duplicates without deleting. Set False to merge.

        Returns:
            Dict with consolidated count, clusters found, and details
        """
        return self._client._post(f"/v1/agents/{self.agent_id}/consolidate", {
            "similarity_threshold": similarity_threshold,
            "dry_run": dry_run,
        })

    def memory_health(self) -> Dict:
        """Get a health assessment of this agent's memory (0-100 score).

        Checks for stale memories, bloat, missing TTL, and other issues.
        Returns actionable recommendations.
        """
        return self._client._get(f"/v1/agents/{self.agent_id}/memory/health")

    # -- Shared Memory (Safe Write) ----------------------------------------

    def share_safe(self, space: str, key: str, value: Any) -> Dict:
        """Write to shared memory with conflict detection.

        Detects when another agent recently wrote to the same key.
        Returns the conflict info so you can decide how to resolve it.

        Args:
            space: Space name
            key: Key within the space
            value: Value to write
        """
        return self._client._post(f"/v1/shared/{space}/safe", {
            "key": key,
            "value": value,
            "author_agent_id": self.agent_id,
        })

    def shared_conflicts(self, space: str = "global", limit: int = 20) -> List[Dict]:
        """List recent write conflicts in a shared memory space."""
        resp = self._client._get(f"/v1/shared/{space}/conflicts", params={"limit": limit})
        return resp.get("conflicts", [])

    # -- Agent Messaging ---------------------------------------------------

    def send_message(self, to_agent: str, message: Any, message_type: str = "info",
                     space: str = "global") -> Dict:
        """Send a message to another agent.

        Args:
            to_agent: Target agent ID
            message: Message content (any JSON-serializable value)
            message_type: "info", "request", "response", or "alert"
            space: Memory space (default "global")
        """
        return self._client._post(f"/v1/agents/{self.agent_id}/messages/send", {
            "to_agent": to_agent, "message": message,
            "message_type": message_type, "space": space,
        })

    def read_messages(self, unread_only: bool = False, space: str = "global",
                      limit: int = 50) -> List[Dict]:
        """Read messages from this agent's inbox."""
        resp = self._client._get(f"/v1/agents/{self.agent_id}/messages/inbox",
                                  params={"unread_only": unread_only, "space": space, "limit": limit})
        return resp.get("messages", [])

    def broadcast(self, message: Any, message_type: str = "info",
                  space: str = "global") -> Dict:
        """Broadcast a message to all agents in a space."""
        return self._client._post(f"/v1/agents/{self.agent_id}/messages/broadcast", {
            "message": message, "message_type": message_type, "space": space,
        })

    # -- Goal Tracking -----------------------------------------------------

    def set_goal(self, goal: str, milestones: Optional[List[str]] = None) -> Dict:
        """Set a goal for this agent with optional milestones."""
        return self._client._post(f"/v1/agents/{self.agent_id}/goal", {
            "goal": goal, "milestones": milestones or [],
        })

    def get_goal(self) -> Dict:
        """Get current goal and progress."""
        return self._client._get(f"/v1/agents/{self.agent_id}/goal")

    def update_progress(self, progress: float = None, milestone_index: int = None,
                        note: str = None) -> Dict:
        """Update progress on the current goal."""
        body = {}
        if progress is not None:
            body["progress"] = progress
        if milestone_index is not None:
            body["milestone_index"] = milestone_index
        if note:
            body["note"] = note
        return self._client._post(f"/v1/agents/{self.agent_id}/goal/progress", body)

    # -- Export / Import ---------------------------------------------------

    def export_memories(self, include_snapshots: bool = False) -> Dict:
        """Export all memories as a portable JSON bundle."""
        return self._client._get(f"/v1/agents/{self.agent_id}/export",
                                  params={"include_snapshots": include_snapshots})

    def import_memories(self, export_data: Dict, overwrite: bool = False) -> Dict:
        """Import memories from an export bundle."""
        export_data["overwrite"] = overwrite
        return self._client._post(f"/v1/agents/{self.agent_id}/import", export_data)

    # -- Filtered Search ---------------------------------------------------

    def search_filtered(self, query: str = None, tags: List[str] = None,
                        importance: str = None, min_age_seconds: int = None,
                        max_age_seconds: int = None, limit: int = 20) -> List[Dict]:
        """Search with combined filters (semantic + tags + importance + time)."""
        body = {"limit": limit}
        if query:
            body["query"] = query
        if tags:
            body["tags"] = tags
        if importance:
            body["importance"] = importance
        if min_age_seconds:
            body["min_age_seconds"] = min_age_seconds
        if max_age_seconds:
            body["max_age_seconds"] = max_age_seconds
        resp = self._client._post(f"/v1/agents/{self.agent_id}/search/filtered", body)
        return resp.get("results", [])

    # -- Aliases (match AgentRuntime API) -----------------------------------

    def remember(self, key: str, value: Any, **kwargs) -> Dict:
        """Alias for write() — matches AgentRuntime API."""
        return self.write(key, value, **kwargs)

    def recall(self, key: str):
        """Alias for read() — matches AgentRuntime API."""
        return self.read(key)

    def recall_similar(self, query: str, limit: int = 10) -> List[Dict]:
        """Alias for search() — matches AgentRuntime API."""
        return self.search(query, limit=limit)

    def recall_history(self, key: str) -> List[Dict]:
        """Alias for history() — matches AgentRuntime API."""
        return self.history(key)

    def __repr__(self):
        return f"Agent({self.agent_id!r})"


class Octopoda:
    """Octopoda cloud client.

    Args:
        api_key: Your API key (starts with sk-octopoda-)
        base_url: API base URL (default: https://api.octapodas.com)
        timeout: Request timeout in seconds (default: 30)
    """

    def __init__(self, api_key: str = None, base_url: str = "https://api.octapodas.com", timeout: int = 30):
        if api_key is None:
            api_key = os.environ.get("OCTOPODA_API_KEY", "")
        if not api_key:
            raise AuthError("api_key is required. Pass it directly or set OCTOPODA_API_KEY environment variable.")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })

    # -- Agent factory ----------------------------------------------------

    def agent(self, agent_id: str, metadata: Optional[Dict] = None) -> Agent:
        """Register (or reconnect to) an agent and return an Agent handle.

        Args:
            agent_id: Unique agent identifier
            metadata: Optional metadata (model, type, etc.)
        """
        body: Dict[str, Any] = {"agent_id": agent_id}
        if metadata:
            body["metadata"] = metadata
        self._post("/v1/agents", body)
        return Agent(self, agent_id)

    def get_agent(self, agent_id: str) -> Agent:
        """Get a handle to an existing agent without re-registering."""
        return Agent(self, agent_id)

    # -- Account ----------------------------------------------------------

    def agents(self, limit: int = 50) -> List[Dict]:
        """List all agents."""
        resp = self._get("/v1/agents", params={"limit": limit})
        return resp.get("agents", [])

    def system_metrics(self) -> Dict:
        """Get system-wide metrics."""
        return self._get("/v1/metrics/system")

    def shared_spaces(self) -> List[Dict]:
        """List all shared memory spaces."""
        resp = self._get("/v1/shared")
        return resp.get("spaces", [])

    def read_shared(self, space: str, key: Optional[str] = None) -> Any:
        """Read from a shared space. If key is None, list all keys."""
        if key:
            return self._get(f"/v1/shared/{space}/{key}")
        return self._get(f"/v1/shared/{space}")

    def recovery_history(self) -> Dict:
        """Get all recovery events."""
        return self._get("/v1/recovery/history")

    def status(self) -> Dict:
        """Get system status."""
        return self._get("/v1/status")

    def me(self) -> Dict:
        """Get current account info."""
        return self._get("/v1/auth/me")

    # -- Webhooks ---------------------------------------------------------

    def add_webhook(self, url: str, events: Optional[List[str]] = None) -> Dict:
        """Register a webhook to receive event notifications.

        Args:
            url: The URL to POST event data to
            events: List of events to subscribe to.
                    Options: agent.crash, agent.recovery, memory.limit, memory.conflict
                    Default: ["agent.crash", "agent.recovery"]
        """
        body: Dict[str, Any] = {"url": url}
        if events:
            body["events"] = events
        return self._post("/v1/webhooks", body)

    def webhooks(self) -> List[Dict]:
        """List all registered webhooks."""
        resp = self._get("/v1/webhooks")
        return resp.get("webhooks", [])

    def remove_webhook(self, webhook_id: str) -> Dict:
        """Remove a webhook by ID."""
        return self._delete(f"/v1/webhooks/{webhook_id}")

    # -- HTTP helpers -----------------------------------------------------

    def _get(self, path: str, params: Optional[Dict] = None) -> Dict:
        return self._request("GET", path, params=params)

    def _post(self, path: str, body: Optional[Dict] = None) -> Dict:
        return self._request("POST", path, json=body)

    def _delete(self, path: str) -> Dict:
        return self._request("DELETE", path)

    def _request(self, method: str, path: str, **kwargs) -> Dict:
        kwargs.setdefault("timeout", self.timeout)
        url = f"{self.base_url}{path}"
        try:
            resp = self._session.request(method, url, **kwargs)
        except requests.ConnectionError:
            raise OctopodaError(f"Cannot connect to {self.base_url}. Is the server running?")
        except requests.Timeout:
            raise OctopodaError(f"Request timed out after {self.timeout}s")

        if resp.status_code == 401:
            raise AuthError("Invalid API key.")
        if resp.status_code == 429:
            retry = int(resp.headers.get("Retry-After", 1))
            raise RateLimitError("Rate limit exceeded.", retry_after=retry)
        if resp.status_code >= 400:
            detail = ""
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise OctopodaError(f"API error {resp.status_code}: {detail}")

        if resp.content:
            return resp.json()
        return {}

    def close(self):
        """Close the HTTP session."""
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __repr__(self):
        return f"Octopoda(base_url={self.base_url!r})"
