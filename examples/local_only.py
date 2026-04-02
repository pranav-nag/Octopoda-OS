"""
Octopoda Local-Only Example
============================
No API key needed. No cloud. No signup. Just persistent agent memory.

Everything runs locally using SQLite. Your data stays on your machine.

Usage:
    pip install octopoda
    python examples/local_only.py
"""

from synrix_runtime.api.runtime import AgentRuntime


def main():
    print("=" * 60)
    print("Octopoda — Local Agent Memory (no cloud, no signup)")
    print("=" * 60)

    # Create an agent — memory persists in local SQLite
    agent = AgentRuntime("local-demo", agent_type="assistant")

    # 1. Basic remember / recall
    print("\n--- Basic Memory ---")
    agent.remember("user_name", "Alex")
    agent.remember("preference", {"theme": "dark", "language": "python"})
    agent.remember("project", "Building an AI assistant for code review")

    name = agent.recall("user_name")
    print(f"Recalled name: {name.value}")
    print(f"  Latency: {name.latency_us:.0f}us")

    prefs = agent.recall("preference")
    print(f"Recalled prefs: {prefs.value}")

    # 2. Memory with importance levels
    print("\n--- Importance Scoring ---")
    agent.remember_important("api_key_location", "stored in .env file", importance="critical")
    agent.remember_important("debug_note", "tried restarting, didn't help", importance="low")

    # 3. Memory with TTL (auto-expires)
    print("\n--- TTL Memory ---")
    agent.remember_with_ttl("temp_session", {"session_id": "abc123"}, ttl_seconds=3600)
    print("Stored temp_session with 1-hour TTL")

    # 4. Conflict detection (write safely)
    print("\n--- Safe Write with Conflict Detection ---")
    agent.remember("db_config", {"host": "localhost", "port": 5432})
    result = agent.remember_safe("db_config", {"host": "production.db", "port": 5432})
    print(f"Conflict detected: {result.has_conflicts}")
    if result.has_conflicts:
        print(f"  Conflicts: {result.conflicts}")

    # 5. Decision logging with audit trail
    print("\n--- Decision Audit Trail ---")
    agent.log_decision(
        decision="Use PostgreSQL for production",
        reasoning="Better concurrency than SQLite for multi-tenant",
        context={"evaluated": ["SQLite", "PostgreSQL", "MySQL"]},
    )
    print("Decision logged with full reasoning and memory snapshot")

    # 6. Memory health check
    print("\n--- Memory Health ---")
    health = agent.memory_health()
    print(f"Health score: {health['score']}/100")
    print(f"Total memories: {health['total_memories']}")
    for issue in health["issues"]:
        print(f"  - {issue}")

    # 7. Recall with confidence scoring
    print("\n--- Confidence-Scored Recall ---")
    result = agent.recall_with_confidence("user_name")
    if result.found:
        print(f"Value: {result.value}")

    # 8. Usage analytics
    print("\n--- Usage Analytics ---")
    analytics = agent.usage_analytics()
    print(f"Total memories: {analytics['total_memories']}")
    print(f"Storage: {analytics['total_size_human']}")
    print(f"Writes: {analytics['writes']}, Reads: {analytics['reads']}")

    # 9. Snapshot for crash recovery
    print("\n--- Snapshot ---")
    snap = agent.snapshot("demo_checkpoint")
    print(f"Snapshot '{snap.label}' captured {snap.keys_captured} keys ({snap.size_bytes} bytes)")

    # 10. Clean shutdown
    agent.shutdown()
    print("\n--- Done ---")
    print("All memories persisted locally in SQLite.")
    print("Run this script again and your agent will remember everything.")


if __name__ == "__main__":
    main()
