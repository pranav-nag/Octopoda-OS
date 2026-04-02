# Octopoda

### The open-source memory operating system for AI agents.

Persistent memory, semantic search, knowledge graphs, loop detection, agent messaging, crash recovery, and real-time observability. Local-first. Works offline. Optionally sync to cloud.

[![PyPI](https://img.shields.io/pypi/v/octopoda)](https://pypi.org/project/octopoda/)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-215%20passing-brightgreen)]()
[![Discord](https://img.shields.io/badge/Discord-Join-7289DA)]()

---

## Quick Start (Local, No Signup)

```bash
pip install octopoda
```

```python
from octopoda import AgentRuntime

agent = AgentRuntime("my_agent")
agent.remember("user_pref", "Alice is vegetarian and lives in London")
result = agent.recall("user_pref")
# Works immediately. SQLite on your machine. No API key. No cloud.
```

That's it. Memory persists across restarts, crashes, and deployments.

---

## Why Octopoda

AI agents forget everything between sessions. Every framework treats memory as disposable. Octopoda fixes that with a proper memory layer that gives agents:

1. **Persistent memory** that survives restarts and crashes
2. **Semantic search** to find memories by meaning, not just exact keys
3. **Loop detection** that catches agents stuck in repetitive patterns
4. **Agent-to-agent messaging** for multi-agent coordination
5. **Knowledge graphs** that map entities and relationships automatically
6. **Real-time observability** so you can see what your agents know and why they make decisions

### How It Compares

| | Octopoda | Mem0 | Zep | LangChain Memory | Raw Vector DB |
|---|---|---|---|---|---|
| **Open source** | Yes (MIT) | No | Partial | Yes | Yes |
| **Local-first** | Yes | No (cloud) | No | No | N/A |
| **Loop detection** | Yes (5-signal) | No | No | No | No |
| **Agent messaging** | Yes | No | No | No | No |
| **Knowledge graph** | Yes | No | No | No | No |
| **Temporal versioning** | Yes | No | No | No | No |
| **Memory health scoring** | Yes | No | No | No | No |
| **Goal tracking** | Yes | No | No | No | No |
| **Export/import** | Yes | No | No | No | No |
| **Crash recovery** | Yes | N/A | No | No | No |
| **Cross-agent sharing** | Yes | Limited | Limited | No | No |
| **MCP server** | Yes (20+ tools) | No | No | No | No |
| **Framework integrations** | LangChain, CrewAI, AutoGen, OpenAI | Some | Some | Own only | None |
| **Pricing** | Free (open core) | Per API call | Flat monthly | Free (basic) | Self-managed |

---

## Core Features

### Semantic Search

Find memories by meaning, not just keys. Uses `bge-small-en-v1.5` (33MB, runs on any CPU).

```bash
pip install octopoda[ai]  # Adds local embeddings
```

```python
agent.remember("bio", "Alice is a vegetarian living in London")
agent.remember("work", "Alice is a senior engineer at Google")

results = agent.recall_similar("where does the user work?")
# Returns: "Alice is a senior engineer at Google" (score: 0.82)
```

### Loop Detection v2

Catches agents stuck in repetitive patterns before they burn through tokens and time. Five detection signals combined into one intelligence report.

```python
status = agent.get_loop_status()
# Returns:
# {
#   "severity": "orange",
#   "score": 45,
#   "signals": [
#     {"type": "write_similarity", "severity": "orange",
#      "detail": "8/10 recent writes are semantically similar",
#      "action": "Call agent.consolidate() to merge duplicates"},
#     {"type": "velocity_spike", "severity": "red",
#      "detail": "12 writes in the last 60 seconds",
#      "action": "Pause the agent. Check for infinite loops."}
#   ],
#   "recovery_suggestions": ["Run agent.consolidate()", "Check agent prompt"]
# }

# Check patterns over time
history = agent.get_loop_history(hours=24)
# Shows hourly breakdown, recurring patterns, spike detection
```

**Five signals:** write similarity, key overwrites, velocity spikes, alert frequency, goal drift. **Escalating severity:** green > yellow > orange > red. Every signal includes what's happening, why, and exactly what to do.

### Agent-to-Agent Messaging

Agents can communicate asynchronously through shared inboxes. No shared database needed.

```python
# Agent A sends a message to Agent B
agent_a.send_message("agent_b", "I found a bug in the auth module", message_type="alert")

# Agent B reads its inbox
messages = agent_b.read_messages(unread_only=True)

# Broadcast to all agents
agent_a.broadcast("Deployment starting in 5 minutes", message_type="alert")
```

### Goal Tracking

Set goals with milestones and track progress. Integrates with drift detection to catch when agents go off-track.

```python
agent.set_goal("Migrate database to PostgreSQL", milestones=[
    "Backup existing data",
    "Create new schema",
    "Migrate records",
    "Run validation tests"
])

agent.update_progress(milestone_index=0, note="Backup completed successfully")
agent.get_goal()
# {"progress": 0.25, "status": "active", "milestones_completed": 1}
```

### Memory Management at Scale

Memory grows. Octopoda keeps it healthy.

```python
# Forget specific memories
agent.forget("outdated_config")
agent.forget_stale(days=30)  # Remove memories older than 30 days
agent.forget_by_tag("temporary")

# Find and merge duplicates
agent.consolidate(dry_run=True)  # Preview first
agent.consolidate()  # Merge semantically similar memories

# Compress old memories into summaries
agent.summarize_old_memories(older_than_days=7)

# Get a health report
health = agent.memory_health()
# {"score": 78, "issues": ["42 stale memories found", "Run consolidate()"]}
```

### Memory Export/Import

Move an agent's brain between systems. Backup before risky operations. Clone knowledge to new agents.

```python
# Export everything
bundle = agent.export_memories()

# Import into a different agent
new_agent.import_memories(bundle)
```

### Filtered Search

Combine semantic queries with tags, importance, and time range.

```python
results = agent.search_filtered(
    query="deployment issues",
    tags=["production"],
    importance="critical",
    max_age_seconds=86400  # Last 24 hours only
)
```

### Knowledge Graph

Auto-extracts entities and relationships from stored memories. No Neo4j, no setup.

```bash
pip install octopoda[nlp]  # Adds spaCy
```

```python
agent.remember("team", "Alice manages the London team with Bob and Carol")

related = agent.related("Alice")
# Returns entity graph with relationships
```

### Crash Recovery

Automatic snapshots with sub-millisecond restore.

```python
agent.snapshot("before_migration")
# ... something goes wrong ...
agent.restore("before_migration")  # Instant recovery
```

### Shared Memory

Agents share knowledge across processes with conflict detection.

```python
# Agent A stores a finding
agent_a.share("research_pool", "analysis", {"findings": "..."})

# Agent B reads it
data = agent_b.read_shared("research_pool", "analysis")

# Safe write with conflict detection
agent_a.share_safe("research_pool", "config", new_value)
```

---

## Framework Integrations

Drop-in memory for the frameworks you already use.

```python
# LangChain
from synrix_runtime.integrations.langchain_memory import SynrixMemory
memory = SynrixMemory(agent_id="my_chain")

# CrewAI
from synrix_runtime.integrations.crewai_memory import SynrixCrewMemory
crew_memory = SynrixCrewMemory(crew_id="research_crew")

# AutoGen
from synrix_runtime.integrations.autogen_memory import SynrixAutoGenMemory
memory = SynrixAutoGenMemory(group_id="dev_team")

# OpenAI Agents SDK
from synrix.integrations.openai_agents import octopoda_tools
tools = octopoda_tools("my_agent")
```

---

## MCP Server

Give Claude, Cursor, or any MCP-compatible AI persistent memory with zero code.

```bash
pip install octopoda[mcp]
```

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "octopoda": {
      "command": "octopoda-mcp"
    }
  }
}
```

**20+ tools available:** memory operations, semantic search, loop detection, goal tracking, agent messaging, memory health, summarization, filtered search, and more.

---

## Cloud API (Optional)

Don't want to manage infrastructure? Use the hosted API at `api.octopodas.com`.

```python
from octopoda import Octopoda

client = Octopoda(api_key="sk-octopoda-...")
agent = client.agent("my_agent")
agent.write("preference", "dark mode")
results = agent.search("user preferences")
```

**Free tier:** 3 agents, 1K memories per agent, 100 AI extractions.
**Pro ($19/mo):** 25 agents, 50K memories, dashboard, Brain system.
**Team ($79/mo):** 100 agents, 200K memories, shared memory, priority support.

Sign up at [octopodas.com](https://octopodas.com)

---

## Installation Options

```bash
pip install octopoda              # Core (local memory, ~5 dependencies)
pip install octopoda[ai]          # + Local embeddings for semantic search
pip install octopoda[nlp]         # + spaCy for knowledge graph extraction
pip install octopoda[mcp]         # + MCP server for Claude/Cursor
pip install octopoda[server]      # + FastAPI cloud server
pip install octopoda[all]         # Everything
```

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OCTOPODA_LLM_PROVIDER` | `none` | LLM for fact extraction: `openai`, `anthropic`, `ollama`, `none` |
| `OCTOPODA_OPENAI_API_KEY` | | OpenAI API key |
| `OCTOPODA_OPENAI_BASE_URL` | `https://api.openai.com/v1` | Any OpenAI-compatible endpoint |
| `OCTOPODA_ANTHROPIC_API_KEY` | | Anthropic API key |
| `OCTOPODA_OLLAMA_URL` | `http://localhost:11434` | Ollama server URL |
| `OCTOPODA_EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | Embedding model (33MB, CPU) |
| `SYNRIX_DATA_DIR` | `~/.synrix/data` | Data directory |

---

## Architecture

```
octopoda/                    — Public entry point (pip install octopoda)
synrix/                      — SDK layer
  sqlite_client.py           — SQLite + WAL + vector search + knowledge graph
  embeddings.py              — Local embeddings (bge-small-en-v1.5, 33MB)
  cloud.py                   — Cloud SDK client (Octopoda class)
  fact_extractor.py          — Multi-provider LLM fact extraction
synrix_runtime/              — Runtime layer
  api/
    runtime.py               — AgentRuntime (core: remember, recall, search, loops, goals, messaging)
    cloud_server.py          — FastAPI cloud API (multi-tenant, auth, rate limiting)
    mcp_server.py            — MCP server (20+ tools, stdio transport)
  monitoring/
    metrics.py               — Performance metrics + anomaly detection
    audit.py                 — Full audit trail
    brain.py                 — Brain Intelligence (Drift Radar, Contradiction Shield)
  integrations/              — LangChain, CrewAI, AutoGen, OpenAI Agents
  dashboard/                 — Real-time monitoring (Flask + SSE)
```

**Local storage:** SQLite with WAL mode. No external database required.
**Cloud storage:** PostgreSQL with pgvector. Multi-tenant with row-level security.
**Embeddings:** `BAAI/bge-small-en-v1.5` — 384 dimensions, 33MB, CPU-only.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions and guidelines.

## Security

See [SECURITY.md](SECURITY.md) for reporting vulnerabilities.

## License

MIT — use it however you want. See [LICENSE](LICENSE).

---

Built by [RYJOX Technologies](https://octopodas.com) | [Documentation](https://octopodas.com/docs) | [Cloud API](https://api.octopodas.com) | [Discord]()
