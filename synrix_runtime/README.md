# Synrix Agent Runtime

Persistent memory kernel for AI agents. Sub-millisecond crash recovery with zero data loss.

## The Problem

- AI agents lose all context when they crash. Rebuilding state takes 30+ seconds.
- Multi-agent systems have no shared persistent memory layer.
- There is no audit trail for agent decisions — you cannot explain what an agent knew when it decided.

## 30-Second Quickstart

```bash
pip install synrix flask flask-cors
```

```python
from synrix_runtime import AgentRuntime

agent = AgentRuntime("my_agent", agent_type="researcher")
agent.remember("finding", {"market_size": "$4.2B", "growth": "34% CAGR"})
value = agent.recall("finding")
print(value)  # RecallResult with your data and latency in microseconds
```

```bash
python synrix_runtime/start.py          # Start runtime + dashboard
python synrix_runtime/start.py --demo   # Start with three-agent demo
```

## Architecture

```
+------------------+     +------------------+     +------------------+
|   Agent Runtime  |     |   Agent Runtime  |     |   Agent Runtime  |
|   (Researcher)   |     |   (Analyst)      |     |   (Writer)       |
+--------+---------+     +--------+---------+     +--------+---------+
         |                        |                        |
         +----------+-------------+-------------+----------+
                    |                           |
              +-----v-----+             +------v------+
              | Shared     |             | Task Bus    |
              | Memory Bus |             | (Handoffs)  |
              +-----+------+             +------+------+
                    |                           |
         +----------v---------------------------v----------+
         |              SYNRIX BACKEND                     |
         |    Persistent Memory Engine (sub-microsecond)   |
         +-------------------------------------------------+
                    |
         +----------v----------+
         |   Runtime Daemon    |
         |  - Heartbeat Monitor|
         |  - Recovery Engine  |
         |  - Anomaly Detector |
         |  - Metrics Collector|
         +---------------------+
```

## System Call API

```python
from synrix_runtime import AgentRuntime

agent = AgentRuntime("agent_01", agent_type="researcher")

# Memory
agent.remember("key", {"data": "value"})    # Write with latency tracking
result = agent.recall("key")                 # Read with latency tracking
results = agent.search("prefix:", limit=50)  # Search by prefix

# Snapshots
agent.snapshot("checkpoint_1")               # Save complete state
agent.restore("checkpoint_1")                # Restore from snapshot

# Shared Memory
agent.share("finding", data, space="team")   # Write to shared space
agent.read_shared("finding", space="team")   # Read from shared space

# Task Handoff
agent.handoff("task_1", "agent_02", payload) # Hand off task
agent.claim_task("task_1")                   # Claim a task
agent.complete_task("task_1", result)        # Complete a task

# Audit Trail
agent.log_decision("chose X", "because Y", context)  # Log decision with memory snapshot
agent.get_stats()                            # Performance metrics
```

## Framework Integrations

### LangChain

```python
from synrix_runtime.integrations.langchain_memory import SynrixMemory

memory = SynrixMemory(agent_id="my_chain")
chain = ConversationChain(llm=llm, memory=memory)
# All conversation history persisted in Synrix
# Survives crashes. Full history available.
```

### CrewAI

```python
from synrix_runtime.integrations.crewai_memory import SynrixCrewMemory

crew_memory = SynrixCrewMemory(crew_id="research_crew")
crew_memory.store_finding("researcher", "market_data", {"value": "$4.2B"})
crew_memory.get_crew_knowledge_base()  # All crew knowledge
crew_memory.crew_snapshot("milestone")  # Snapshot entire crew
```

### AutoGen

```python
from synrix_runtime.integrations.autogen_memory import SynrixAutoGenMemory

memory = SynrixAutoGenMemory(group_id="my_group")
memory.store_message("agent_a", "agent_b", "Hello")
history = memory.get_conversation_history()
```

### OpenAI Agents SDK

```python
from synrix_runtime.integrations.openai_agents import SynrixOpenAIMemory

memory = SynrixOpenAIMemory()
memory.store_thread_state("thread_123", state)
restored = memory.restore_thread("thread_123")
```

## Dashboard

The real-time dashboard runs on `http://localhost:7842` and provides:

- **Agent Map**: D3.js force-directed graph of all agents with state-colored nodes
- **Memory Explorer**: Browse every key in every namespace with JSON viewer
- **Audit & Replay**: Timeline of all decisions with full memory snapshots
- **Performance**: Agent comparison, latency charts, anomaly detection
- **Recovery Console**: Watch crash recovery happen in real time with step-by-step timings
- **Shared Memory Bus**: Visualize inter-agent communication

All data is real. Every number comes from actual Synrix queries. No mock data.

## Performance

All latencies measured with `time.perf_counter_ns()`:

| Operation | Latency |
|-----------|---------|
| Write | ~50-200us |
| Read | ~10-100us |
| Query (prefix) | ~20-150us |
| Snapshot (20 keys) | ~500-1500us |
| Full Recovery | ~800-2000us |

## How Recovery Works

1. Agent crashes (heartbeat timeout or simulated)
2. Daemon detects crash within 3 seconds
3. Recovery orchestrator runs 5-step sequence:
   - Query agent memory namespace
   - Query agent snapshots
   - Query agent task states
   - Reconstruct complete state
   - Write recovered state
4. Each step individually timed in microseconds
5. Agent resumes with full context — zero data loss
6. Total recovery time: typically under 2ms

## CLI

```bash
python -m synrix_runtime.cli.synrix_cli status              # System status
python -m synrix_runtime.cli.synrix_cli agents list          # List agents
python -m synrix_runtime.cli.synrix_cli agents inspect <id>  # Agent detail
python -m synrix_runtime.cli.synrix_cli memory browse <id>   # Browse memory
python -m synrix_runtime.cli.synrix_cli memory search <pfx>  # Search keys
python -m synrix_runtime.cli.synrix_cli audit replay <id>    # Replay audit
python -m synrix_runtime.cli.synrix_cli recovery history     # Recovery log
python -m synrix_runtime.cli.synrix_cli demo run             # Run demo
python -m synrix_runtime.cli.synrix_cli dashboard            # Start dashboard
python -m synrix_runtime.cli.synrix_cli export <id>          # Export state
```

## Project Structure

```
synrix_runtime/
  core/           Daemon, registry, namespace, recovery, heartbeat
  api/            AgentRuntime, system calls, shared memory, task bus
  monitoring/     Metrics, anomaly detection, performance, audit
  integrations/   LangChain, CrewAI, AutoGen, OpenAI Agents
  dashboard/      Flask app, API routes, SSE streaming, static frontend
  demo/           Three-agent demo, crash recovery demo, multi-crew demo
  cli/            Command line interface
  start.py        Single entry point
```

## License

MIT
