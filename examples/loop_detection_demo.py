"""
Octopoda Loop Detection Demo
==============================
Demonstrates 3 types of agent loops that Octopoda catches automatically.

Run the server first:
    pip install octopoda[server]
    octopoda

Then run this script:
    python examples/loop_detection_demo.py

Open http://localhost:7842 to watch it happen in real time.
"""

import requests
import time
import sys
import random

BASE = "http://localhost:8741"

def api(method, path, data=None):
    if method == "POST":
        r = requests.post(f"{BASE}{path}", json=data, timeout=15)
    elif method == "PUT":
        r = requests.put(f"{BASE}{path}", json=data, timeout=15)
    else:
        r = requests.get(f"{BASE}{path}", timeout=15)
    return r

def register(agent_id):
    api("POST", "/v1/agents", {"agent_id": agent_id})

def remember(agent_id, key, value, tags=None):
    data = {"key": key, "value": value}
    if tags:
        data["tags"] = tags
    return api("POST", f"/v1/agents/{agent_id}/remember", data)

def loop_status(agent_id):
    return api("GET", f"/v1/agents/{agent_id}/loops/status").json()

def print_status(agent_id):
    status = loop_status(agent_id)
    severity = status.get("severity", "?")
    score = status.get("score", "?")
    loop_type = status.get("loop_type", "none")

    colors = {"green": "\033[92m", "yellow": "\033[93m", "orange": "\033[33m", "red": "\033[91m"}
    reset = "\033[0m"
    color = colors.get(severity, "")

    print(f"  {color}[{severity.upper()}]{reset} Score: {score}/100 | Type: {loop_type}")

    if status.get("cost"):
        cost = status["cost"]
        print(f"  Cost: ${cost.get('estimated_wasted', 0):.4f} wasted | ${cost.get('estimated_saved', 0):.4f} saved")

    if status.get("prediction"):
        pred = status["prediction"]
        print(f"  Prediction: {pred.get('warning', '')}")

    if status.get("replay"):
        print(f"  Replay: {len(status['replay'])} writes captured")

    for signal in status.get("signals", []):
        print(f"    - {signal['type']}: {signal['detail']}")

    if status.get("root_cause"):
        print(f"  Root cause: {status['root_cause'][:100]}...")
    print()


def divider(title):
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)
    print()


# ============================================================
# CHECK SERVER
# ============================================================
try:
    r = requests.get(f"{BASE}/health", timeout=5)
    if r.status_code != 200:
        raise Exception()
except:
    print("Server not running. Start it with: octopoda")
    print("Then open http://localhost:7842 to watch the demo.")
    sys.exit(1)

# Set model for cost tracking
api("PUT", "/v1/settings", {"llm_model": "gpt-4o"})

print()
print("  OCTOPODA LOOP DETECTION DEMO")
print("  Open http://localhost:7842 to watch in real time")
print()
input("  Press Enter to start...\n")


# ============================================================
# DEMO 1: RETRY LOOP
# ============================================================
divider("DEMO 1: Retry Loop")
print("  An agent that keeps overwriting the same key with similar values.")
print("  This happens when a prompt tells the agent to 'update preferences'")
print("  on every turn, even when nothing changed.")
print()

register("support-bot")

# Store some normal memories first
remember("support-bot", "customer:alice:plan", "Pro plan, renewed annually")
remember("support-bot", "customer:alice:issue", "API key configuration - resolved")
remember("support-bot", "kb:api-keys", "API keys can be regenerated in Settings > API Keys")
print("  Stored 3 normal memories for support-bot")
time.sleep(1)

print("  Now simulating a retry loop...\n")
for i in range(8):
    variations = [
        "Customer Alice is on Pro plan, renewed annually, very happy",
        "Alice - Pro plan subscriber, annual renewal, satisfied customer",
        "Pro plan user Alice, renews yearly, positive sentiment",
        "Alice has Pro subscription renewed annually, customer satisfied",
        "Pro annual plan holder Alice, happy with service",
        "Customer profile: Alice, Pro plan, annual, satisfied",
        "Alice - Pro tier, yearly renewal, good standing",
        "Pro subscriber Alice, annual billing, positive feedback",
    ]
    remember("support-bot", "customer:alice:status", variations[i % len(variations)])
    print(f"  Write {i+1}/8: {variations[i % len(variations)][:60]}...")
    time.sleep(0.5)

time.sleep(2)
print("\n  Checking loop status:")
print_status("support-bot")
input("  Press Enter for Demo 2...\n")


# ============================================================
# DEMO 2: POLLING LOOP
# ============================================================
divider("DEMO 2: Polling Loop")
print("  An agent that writes on every tick instead of only when data changes.")
print("  This is common with monitoring agents that store metrics every second")
print("  even when nothing is different.")
print()

register("metrics-collector")

print("  Simulating rapid polling writes...\n")
for i in range(15):
    remember("metrics-collector", f"metric:cpu:{int(time.time())}",
             f"CPU usage: {random.uniform(45, 55):.1f}% at {time.strftime('%H:%M:%S')}")
    print(f"  Tick {i+1}/15: CPU metric stored")
    time.sleep(0.3)

time.sleep(2)
print("\n  Checking loop status:")
print_status("metrics-collector")
input("  Press Enter for Demo 3...\n")


# ============================================================
# DEMO 3: OSCILLATION
# ============================================================
divider("DEMO 3: Oscillation")
print("  An agent that keeps changing its mind. Writes different values to")
print("  the same key back and forth. Usually means conflicting instructions")
print("  in the prompt or two systems disagreeing.")
print()

register("decision-agent")

# Store some context first
remember("decision-agent", "context:budget", "Q4 budget is $50,000")
remember("decision-agent", "context:deadline", "Project deadline is March 15")
print("  Stored context for decision-agent")
time.sleep(1)

print("  Simulating oscillation...\n")
decisions = [
    ("Go with vendor A - cheaper, faster delivery", "decision A"),
    ("Actually vendor B - better quality, worth the wait", "decision B"),
    ("No, vendor A is the right call - budget is tight", "decision A"),
    ("Reconsidering vendor B - quality issues with A", "decision B"),
    ("Final answer: vendor A - can't exceed budget", "decision A"),
    ("Wait - vendor B offered a discount, switching back", "decision B"),
    ("Vendor A confirmed - locking in the decision", "decision A"),
    ("New info: vendor B has faster shipping now, switching", "decision B"),
]

for i, (value, label) in enumerate(decisions):
    remember("decision-agent", "recommendation:vendor", value)
    print(f"  Write {i+1}/8: [{label}] {value[:50]}...")
    time.sleep(0.8)

time.sleep(2)
print("\n  Checking loop status:")
print_status("decision-agent")


# ============================================================
# SUMMARY
# ============================================================
divider("DEMO COMPLETE")
print("  Three loop types detected:")
print()
print("  1. RETRY LOOP (support-bot)")
print("     Same key, similar values - agent retrying unnecessarily")
print()
print("  2. POLLING LOOP (metrics-collector)")
print("     High velocity writes - agent storing on every tick")
print()
print("  3. OSCILLATION (decision-agent)")
print("     Same key, different values - agent can't make up its mind")
print()
print("  Check the dashboard at http://localhost:7842 to see:")
print("    - Loop Intelligence page: full signal breakdown + cost estimation")
print("    - Agents page: all 3 agents with scores")
print("    - Memory Explorer: version history showing the repeated writes")
print()
print("  All three loops were caught automatically by Octopoda.")
print("  No configuration needed. Just create an agent and it monitors itself.")
print()
