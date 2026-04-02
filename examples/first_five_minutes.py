"""
Octopoda - Your First 5 Minutes
================================
Run this script after installing Octopoda and watch your dashboard light up.

    pip install octopoda
    python first_five_minutes.py

Then open your dashboard and explore every tab.
"""

import time
import os
from synrix import Octopoda

API_KEY = os.environ.get("OCTOPODA_API_KEY", "YOUR_API_KEY_HERE")

print()
print("=" * 60)
print("  OCTOPODA - Your First 5 Minutes")
print("=" * 60)
print()

client = Octopoda(api_key=API_KEY)

# Check connection
account = client.me()
print(f"Connected as: {account.get('email', 'unknown')}")
print(f"Plan: {account.get('plan', 'free')}")
print()

# ---------------------------------------------
# STEP 1: Create three agents
# ---------------------------------------------
print("[1/8] Creating agents...")

support = client.agent("support-bot", metadata={"role": "customer support", "version": "1.0"})
researcher = client.agent("research-bot", metadata={"role": "research assistant"})
assistant = client.agent("personal-assistant", metadata={"role": "personal AI"})

print("      support-bot        [ok]")
print("      research-bot       [ok]")
print("      personal-assistant  [ok]")
print()

# ---------------------------------------------
# STEP 2: Write memories (basic + batch)
# ---------------------------------------------
print("[2/8] Writing memories...")

support.write("customer:sarah", {
    "name": "Sarah Chen",
    "company": "Acme Corp",
    "plan": "enterprise",
    "last_issue": "API timeout on batch uploads"
}, tags=["customer", "enterprise"])

support.write("customer:marcus", {
    "name": "Marcus Johnson",
    "company": "StartupXYZ",
    "plan": "free",
    "last_issue": "Rate limiting confusion"
}, tags=["customer", "free-tier"])

support.write("kb:common_fix:timeout",
    "Timeouts over 5s usually mean the embedding model is cold-starting. First request after 30min idle takes 2-3s extra.",
    tags=["knowledge-base", "timeout"])

researcher.write_batch([
    {"key": "finding:ai_memory_market", "value": "$2.1B AI memory market projected by 2027", "tags": ["market-research"]},
    {"key": "finding:agent_frameworks", "value": "LangChain, CrewAI, AutoGen are top 3 agent frameworks by GitHub stars", "tags": ["market-research"]},
    {"key": "finding:developer_pain", "value": "78% of agent developers cite memory persistence as their top infrastructure gap", "tags": ["market-research", "important"]},
])

assistant.write("preference:communication", "Prefers concise answers, no fluff, bullet points over paragraphs")
assistant.write("preference:schedule", "Most productive in mornings, meetings after 2pm")
assistant.write("fact:project", "Currently building an AI-powered code review tool using CrewAI")

print("      11 memories written across 3 agents [ok]")
print()

# ---------------------------------------------
# STEP 3: Important memories + TTL
# ---------------------------------------------
print("[3/8] Writing important + expiring memories...")

support.write_important(
    "escalation:acme_corp",
    "Acme Corp renewal is next week. Any support ticket from them is top priority.",
    importance="critical",
    tags=["escalation", "urgent"]
)

support.write_ttl(
    "notice:maintenance_window",
    "Scheduled maintenance tonight 2am-4am UTC. Expect 30s of downtime.",
    ttl_seconds=3600,
    tags=["maintenance"]
)

print("      1 critical memory written [ok]")
print("      1 TTL memory (expires in 1 hour) [ok]")
print()

# ---------------------------------------------
# STEP 4: Version history (update a memory)
# ---------------------------------------------
print("[4/8] Creating version history...")

assistant.write("preference:framework", "Using LangChain for all agent projects")
time.sleep(0.5)
assistant.write("preference:framework", "Switched to CrewAI, better multi-agent support")
time.sleep(0.5)
assistant.write("preference:framework", "CrewAI for orchestration, LangChain for simple chains only")

history = assistant.history("preference:framework")
print(f"      preference:framework now has {len(history)} versions")
print("      v1: Using LangChain for all agent projects")
print("      v2: Switched to CrewAI")
print("      v3: CrewAI for orchestration, LangChain for simple chains")
print("      -> Check Memory Explorer to see the full version timeline")
print()

# ---------------------------------------------
# STEP 5: Conflict detection
# ---------------------------------------------
print("[5/8] Testing conflict detection...")

conflict_result = support.check_conflicts(
    "customer:sarah",
    {"name": "Sarah Chen", "company": "Acme Corp", "plan": "free"}
)

conflicts = conflict_result.get("conflicts", [])
if conflicts:
    print("      Conflict detected: Sarah's plan changed from 'enterprise' to 'free'")
else:
    print("      Conflict check completed [ok]")
print()

# ---------------------------------------------
# STEP 6: Shared memory between agents
# ---------------------------------------------
print("[6/8] Sharing memory between agents...")

support.share("team-knowledge", "customer:top_request",
    "Memory debugging tools. 7 out of 10 users asked for visual memory inspection.")

researcher.share("team-knowledge", "market:insight",
    "Competitors lack real-time dashboards. This is our differentiator.")

assistant.share("team-knowledge", "project:status",
    "MVP launched, 55 users in first 48 hours, 14 active builders.")

print("      3 items shared in 'team-knowledge' space [ok]")
print("      All 3 agents can now read each other's insights")
print()

# ---------------------------------------------
# STEP 7: Semantic search
# ---------------------------------------------
print("[7/8] Semantic search (finding by meaning, not key)...")

time.sleep(2)

results = researcher.search("what are developers struggling with", limit=3)
print("      Query: 'what are developers struggling with'")
print(f"      Found {len(results)} relevant memories:")
for r in results[:3]:
    key = r.get("key", "unknown")
    value = str(r.get("value", ""))[:80]
    print(f"        {key}: {value}")
print()

# ---------------------------------------------
# STEP 8: Snapshot + audit trail
# ---------------------------------------------
print("[8/8] Taking a snapshot and logging a decision...")

snap = support.snapshot(label="first-five-minutes")
print(f"      Snapshot created [ok]")

support.decide(
    decision="escalate",
    reasoning="Acme Corp is a high-value customer with renewal next week",
    context={"customer": "sarah", "issue": "API timeout", "severity": "high"}
)
print("      Audit decision logged [ok]")
print()

# ---------------------------------------------
# DONE
# ---------------------------------------------
print("=" * 60)
print("  DONE! Open your dashboard and explore:")
print("=" * 60)
print()
print("  Overview        -> 3 agents running with health scores")
print("  Agents          -> Click any agent for latency + memories")
print("  Memory Explorer -> Browse memories, click for version history")
print("  Shared Memory   -> 'team-knowledge' with cross-agent data")
print("  Performance     -> Write/read latency graphs")
print("  Analytics       -> Operations breakdown by agent")
print("  Audit Trail     -> Every operation logged + your escalation decision")
print("  Recovery        -> Snapshot ready to restore anytime")
print("  Anomalies       -> Brain system monitoring for loops + drift")
print()
print("  Dashboard: https://octopoda.lovable.app")
print()

client.close()
