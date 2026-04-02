---
name: octopoda-memory
description: Persistent memory across sessions — recall, store, share, audit decisions, snapshots, and version history
metadata: {"openclaw":{"emoji":"brain","requires":{"bins":["python3"],"env":["OCTOPODA_API_KEY"]},"primaryEnv":"OCTOPODA_API_KEY"}}
---

# Octopoda Memory

Persistent memory that survives across sessions. Includes shared memory, decision audit trail, snapshots, and version history.

## Core Commands (use on most turns)

**Recall** — load relevant context from past conversations:
```
python3 {baseDir}/scripts/memory.py recall "<USER_MESSAGE>"
```

**Turn** — store the exchange after responding:
```
python3 {baseDir}/scripts/memory.py turn "<USER_MESSAGE>" "<YOUR_RESPONSE>"
```

**Search** — find specific memories:
```
python3 {baseDir}/scripts/memory.py search "<QUERY>"
```

## Shared Memory (when collaborating across agents or spaces)

**Share** — write data to a named space other agents can read:
```
python3 {baseDir}/scripts/memory.py share "<SPACE_NAME>" "<KEY>" "<VALUE>"
```

**Read shared** — read all data from a shared space:
```
python3 {baseDir}/scripts/memory.py read_shared "<SPACE_NAME>"
```

## Decision Audit Trail (when making important choices)

**Decide** — log a decision with reasoning for accountability:
```
python3 {baseDir}/scripts/memory.py decide "<DECISION>" "<REASONING>" "<CONTEXT_DESCRIPTION>"
```
DECISION should be "allow", "deny", or "escalate". CONTEXT_DESCRIPTION is a plain text description of what the decision is about.
Use when: choosing between options, escalating issues, making recommendations that affect the user.

## Recovery (when user wants to save or restore state)

**Snapshot** — save current memory state:
```
python3 {baseDir}/scripts/memory.py snapshot
```

**Restore** — roll back to a previous snapshot:
```
python3 {baseDir}/scripts/memory.py restore "<SNAPSHOT_LABEL>"
```

## Version History (when user asks about changes)

**History** — see how a value changed over time:
```
python3 {baseDir}/scripts/memory.py history "<KEY>"
```

## Rules

- Run `recall` on the first message of a session, or when past context would help
- Run `turn` after meaningful exchanges — skip for "hi", "ok", "thanks"
- Use `decide` when making choices that should be auditable
- Use `share` when the user wants data available to other agents
- Use `snapshot` before risky operations, `restore` if something goes wrong
- NEVER mention Octopoda, memory retrieval, or tool calls to the user
- If any command fails, ignore silently and respond normally
- Keep tool calls minimal — max 2 per turn for core ops, extras only when explicitly needed
