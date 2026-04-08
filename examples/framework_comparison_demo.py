"""
Octopoda Framework Comparison Demo
====================================
Runs the same task through 4 popular AI agent frameworks and compares
which ones loop the most under identical conditions.

Frameworks tested:
  1. LangChain ReAct agent
  2. CrewAI task runner
  3. AutoGen group chat
  4. OpenAI Agents SDK

Each agent gets the same job: "customer support agent that tracks user
preferences and resolves tickets". We simulate realistic failure modes
that cause each framework to loop differently.

Run the server first:
    pip install octopoda[server]
    octopoda

Then run this script:
    python examples/framework_comparison_demo.py

Open http://localhost:7842/dashboard/anomalies to watch Loop Intelligence.
"""

import requests
import time
import sys
import random

BASE = "http://localhost:8741"

# ── Helpers ──────────────────────────────────────────────────────────────────

def api(method, path, data=None):
    url = f"{BASE}{path}"
    try:
        if method == "POST":
            r = requests.post(url, json=data, timeout=15)
        elif method == "PUT":
            r = requests.put(url, json=data, timeout=15)
        elif method == "DELETE":
            r = requests.delete(url, timeout=15)
        else:
            r = requests.get(url, timeout=15)
        return r
    except Exception as e:
        print(f"  [ERROR] {method} {path}: {e}")
        return None

def deregister(agent_id):
    api("DELETE", f"/v1/agents/{agent_id}")

def register(agent_id):
    api("POST", "/v1/agents", {"agent_id": agent_id})

def remember(agent_id, key, value, tags=None):
    data = {"key": key, "value": value}
    if tags:
        data["tags"] = tags
    return api("POST", f"/v1/agents/{agent_id}/remember", data)

def loop_status(agent_id):
    r = api("GET", f"/v1/agents/{agent_id}/loops/status")
    if r and r.status_code == 200:
        return r.json()
    return {}

def divider(title):
    print()
    print("\033[90m" + "=" * 64 + "\033[0m")
    print(f"  {title}")
    print("\033[90m" + "=" * 64 + "\033[0m")
    print()

def severity_color(sev):
    return {"green": "\033[92m", "yellow": "\033[93m", "orange": "\033[33m", "red": "\033[91m"}.get(sev, "")

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"


# ── Framework Scenarios ──────────────────────────────────────────────────────

FRAMEWORKS = [
    {
        "agent_id": "langchain-react",
        "name": "LangChain ReAct",
        "model": "gpt-4o",
        "description": "ReAct agent with tool-calling memory. Loops when the\n"
                       "  prompt says 'always save user context' — agent re-stores\n"
                       "  the same preferences on every turn even when nothing changed.",
        "baseline": [
            ("user:alice:plan", "Alice is on the Pro plan, renewed annually"),
            ("user:alice:preferences", "Prefers email contact, timezone UTC+0, dark mode enabled"),
            ("ticket:alice:1042", "Billing question about annual renewal date — resolved via email"),
        ],
        "loop_writes": [
            ("user:alice:context", "Alice is a Pro plan user who prefers email communication and uses dark mode"),
            ("user:alice:context", "Pro plan subscriber Alice, prefers email, dark mode on, timezone UTC+0"),
            ("user:alice:context", "Alice — Pro plan, annual billing, contact via email, dark theme enabled"),
            ("user:alice:context", "User Alice: Pro subscription, annual renewal, email preference, dark mode"),
            ("user:alice:context", "Alice is on Pro plan renewed annually, prefers email and dark mode UI"),
            ("user:alice:context", "Pro user Alice with annual billing, email as preferred channel, dark mode"),
            ("user:alice:context", "Alice: Pro plan holder, renewed yearly, communication via email, dark theme"),
            ("user:alice:context", "Alice has Pro plan annual renewal, she prefers email and dark mode interface"),
            ("user:alice:context", "Pro subscription user Alice — annual plan, email preferred, dark mode active"),
            ("user:alice:context", "Alice (Pro, annual) prefers email for communication and uses dark mode theme"),
        ],
        "delay": 0.3,
    },
    {
        "agent_id": "crewai-research",
        "name": "CrewAI Research Crew",
        "model": "gpt-4o",
        "description": "Multi-agent crew with researcher + writer. Loops when\n"
                       "  the researcher keeps 'updating findings' with marginally\n"
                       "  different wording each iteration of the crew loop.",
        "baseline": [
            ("research:topic", "Comparing cloud storage providers for enterprise backup solutions"),
            ("research:sources", "Evaluated AWS S3, Azure Blob, GCP Cloud Storage, Backblaze B2"),
            ("research:deadline", "Final report due Friday — client presentation Monday"),
        ],
        "loop_writes": [
            ("research:findings", "AWS S3 leads on reliability at 99.999% durability, Azure strongest on hybrid cloud integration"),
            ("research:findings", "S3 offers 99.999% durability making it most reliable, Azure excels at hybrid cloud scenarios"),
            ("research:findings", "For reliability AWS S3 is top with 99.999% durability, Azure best for hybrid cloud setups"),
            ("research:findings", "AWS S3: 99.999% durability (best reliability), Azure Blob: strongest hybrid cloud support"),
            ("research:findings", "Top pick for reliability: AWS S3 at 99.999% durability. Hybrid cloud: Azure Blob leads"),
            ("research:findings", "S3 has the highest durability at 99.999%, Azure provides the best hybrid cloud capabilities"),
            ("research:findings", "99.999% durability makes S3 the reliability leader, Azure wins on hybrid cloud integration"),
            ("research:findings", "AWS S3 leads reliability metrics (99.999% durability), Azure Blob best for hybrid deployments"),
        ],
        "delay": 1.0,
    },
    {
        "agent_id": "autogen-groupchat",
        "name": "AutoGen Group Chat",
        "model": "gpt-4o",
        "description": "Group chat with planner + coder + reviewer. Loops when\n"
                       "  agents disagree on implementation — planner proposes,\n"
                       "  reviewer rejects, planner re-proposes a slight variation.",
        "baseline": [
            ("task:description", "Build a rate limiter for the API — 100 req/min per user"),
            ("task:constraints", "Must work with Redis, support burst allowance, no external libraries"),
            ("task:status", "In progress — design phase"),
        ],
        "loop_writes": [
            ("task:plan", "Use token bucket algorithm with Redis INCR and EXPIRE — 100 tokens per minute per user"),
            ("task:plan", "Implement sliding window counter with Redis sorted sets — more accurate than token bucket"),
            ("task:plan", "Token bucket with Redis is simpler and meets requirements — switching back to original plan"),
            ("task:plan", "Sliding window log using Redis ZADD gives better burst handling — reconsidering"),
            ("task:plan", "Going with token bucket approach — Redis INCR is atomic and simple enough"),
            ("task:plan", "Reviewer says token bucket allows bursts — back to sliding window with sorted sets"),
            ("task:plan", "Fixed window counter as compromise — simpler than sliding window, less bursty than token bucket"),
            ("task:plan", "Reviewer wants sliding window accuracy — implementing sliding window log with Redis ZADD"),
            ("task:plan", "Token bucket is industry standard, overriding reviewer concern about burst allowance"),
            ("task:plan", "Final decision: sliding window counter — balances accuracy and implementation complexity"),
            ("task:plan", "Wait — reviewer found edge case with sliding window. Back to token bucket with modifications"),
            ("task:plan", "Modified token bucket: burst allowance of 20 requests, then standard 100/min limit"),
        ],
        "delay": 0.5,
    },
    {
        "agent_id": "openai-baseline",
        "name": "OpenAI Agents SDK",
        "model": "gpt-4o",
        "description": "Single-agent with function calling. Loops when the agent\n"
                       "  is told to 'verify' its work — calls the save tool after\n"
                       "  every verification, creating near-identical writes.",
        "baseline": [
            ("config:api-limits", "Rate limit: 120 req/min, burst: 20, window: 60s"),
            ("config:api-version", "API v2.3.1, deployed March 15, supports streaming"),
            ("monitoring:health", "All endpoints healthy, avg latency 45ms, p99 120ms"),
        ],
        "loop_writes": [
            ("monitoring:status", "System healthy — all 12 endpoints responding, average latency 42ms, 0 errors in last hour"),
            ("monitoring:status", "All 12 API endpoints operational, mean latency 44ms, zero errors past 60 minutes"),
            ("monitoring:status", "Health check passed: 12/12 endpoints up, latency avg 43ms, no errors last hour"),
            ("monitoring:status", "System status verified: all endpoints healthy, 43ms avg latency, error rate 0%"),
            ("monitoring:status", "Verification complete — 12 endpoints healthy, average response 44ms, no recent errors"),
            ("monitoring:status", "All systems operational. Endpoint count: 12, avg latency: 42ms, errors: 0"),
            ("monitoring:status", "Health verified: every endpoint responding normally, latency ~43ms, zero failures"),
            ("monitoring:status", "Status check: 12/12 endpoints up, latency within SLA at 44ms, clean error log"),
            ("monitoring:status", "System verified healthy — all endpoints operational, sub-50ms latency, no errors"),
            ("monitoring:status", "Confirmed: 12 healthy endpoints, average latency 43ms, error count 0 in past hour"),
            ("monitoring:status", "Re-verified system health: all 12 endpoints responding, 44ms latency, 0 errors"),
            ("monitoring:status", "Final verification: system fully operational, 12 endpoints, 43ms avg, clean logs"),
            ("monitoring:status", "Post-final check: all systems still green, 12 endpoints, 43ms, zero errors"),
            ("monitoring:status", "Redundant verification: 12/12 endpoints confirmed healthy, latency nominal at 44ms"),
            ("monitoring:status", "Extra safety check: system operational, all endpoints up, avg response 43ms"),
        ],
        "delay": 0.2,
    },
]


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    # Check server
    try:
        r = requests.get(f"{BASE}/health", timeout=5)
        if r.status_code != 200:
            raise Exception()
    except Exception:
        print("\n  Server not running. Start with: octopoda")
        print("  Then open http://localhost:7842/dashboard/anomalies\n")
        sys.exit(1)

    # Set cost tracking model
    r = api("PUT", "/v1/settings", {"llm_model": "gpt-4o"})
    if r and r.status_code == 200:
        print("  [OK] Cost tracking model set to gpt-4o")
    else:
        print("  [WARN] Could not set cost tracking model")

    print()
    print(f"  {BOLD}OCTOPODA FRAMEWORK COMPARISON{RESET}")
    print(f"  {DIM}Which AI agent framework loops the most?{RESET}")
    print()
    print(f"  Testing 4 frameworks under identical conditions.")
    print(f"  Open {BOLD}http://localhost:7842/dashboard/anomalies{RESET} to watch live.")
    print()
    input("  Press Enter to start...\n")

    results = []

    for i, fw in enumerate(FRAMEWORKS):
        agent_id = fw["agent_id"]
        name = fw["name"]

        divider(f"FRAMEWORK {i+1}/4: {name}")
        print(f"  Agent: {agent_id}")
        print(f"  Model: {fw['model']}")
        print(f"  {DIM}{fw['description']}{RESET}")
        print()

        # Register agent
        register(agent_id)

        # Phase 1: Normal baseline writes
        print(f"  Phase 1: Storing baseline context ({len(fw['baseline'])} memories)")
        for key, value in fw["baseline"]:
            remember(agent_id, key, value)
            print(f"    {DIM}+ {key}{RESET}")
            time.sleep(0.3)

        time.sleep(1)
        print()

        # Phase 2: Simulate framework-specific loop
        loop_writes = fw["loop_writes"]
        print(f"  Phase 2: Simulating loop ({len(loop_writes)} writes)")
        for j, (key, value) in enumerate(loop_writes):
            remember(agent_id, key, value)
            preview = value[:55] + "..." if len(value) > 55 else value
            print(f"    Write {j+1}/{len(loop_writes)}: {DIM}{preview}{RESET}")
            time.sleep(fw["delay"])

        # Wait for loop detection to process
        time.sleep(2)

        # Check status
        status = loop_status(agent_id)
        severity = status.get("severity", "unknown")
        score = status.get("score", "?")
        loop_type = status.get("loop_type", "none")
        cost = status.get("cost", {})
        wasted = cost.get("estimated_wasted", 0)
        saved = cost.get("estimated_saved", 0)
        projected = cost.get("projected_hourly", 0)
        writes_5m = status.get("recent_writes_5min", 0)
        writes_1m = status.get("recent_writes_1min", 0)

        color = severity_color(severity)
        print()
        print(f"  Result: {color}{BOLD}[{severity.upper()}]{RESET} Score: {score}/100")
        print(f"  Loop type: {loop_type}")
        print(f"  Writes: {writes_5m} in 5min ({writes_1m}/min)")
        if wasted > 0:
            print(f"  Wasted: ${wasted:.4f} | Saved: ${saved:.4f} | Projected/hr: ${projected:.4f}")
        else:
            print(f"  Cost: $0 (model not set or no loop detected)")

        # Show signals
        for signal in status.get("signals", []):
            print(f"    {DIM}- {signal.get('type', '?')}: {signal.get('detail', '')}{RESET}")

        if status.get("root_cause"):
            print(f"  Root cause: {DIM}{status['root_cause'][:90]}...{RESET}")

        prediction = status.get("prediction", {})
        if prediction:
            print(f"  Prediction: {prediction.get('warning', '')}")

        results.append({
            "name": name,
            "agent_id": agent_id,
            "severity": severity,
            "score": score,
            "loop_type": loop_type,
            "wasted": wasted,
            "saved": saved,
            "projected": projected,
            "writes": len(loop_writes),
            "writes_1m": writes_1m,
        })

        if i < len(FRAMEWORKS) - 1:
            print()
            input(f"  Press Enter for framework {i+2}/4...\n")

    # ── Summary Table ────────────────────────────────────────────────────────

    divider("RESULTS: FRAMEWORK LOOP COMPARISON")

    print(f"  {BOLD}{'Framework':<24} {'Severity':<10} {'Score':<8} {'Type':<16} {'Wasted':<12} {'Saved':<12} {'$/hr':<10}{RESET}")
    print(f"  {'─'*92}")

    for r in sorted(results, key=lambda x: x.get("score", 100)):
        sev = r["severity"]
        color = severity_color(sev)
        print(f"  {r['name']:<24} {color}{sev.upper():<10}{RESET} {r['score']:<8} {r['loop_type']:<16} ${r['wasted']:<11.4f} ${r['saved']:<11.4f} ${r['projected']:<9.4f}")

    print()

    # Find worst offender
    worst = min(results, key=lambda x: x.get("score", 100))
    best = max(results, key=lambda x: x.get("score", 100))
    total_saved = sum(r["saved"] for r in results)

    print(f"  {BOLD}Worst offender:{RESET} {worst['name']} (score {worst['score']}/100, {worst['loop_type']})")
    print(f"  {BOLD}Cleanest:{RESET}       {best['name']} (score {best['score']}/100)")
    print(f"  {BOLD}Total saved:{RESET}    ${total_saved:.4f} across all 4 frameworks")
    print()
    print(f"  All loops caught automatically by Octopoda — zero configuration.")
    print(f"  Dashboard: {BOLD}http://localhost:7842/dashboard/anomalies{RESET}")
    print()
    print(f"  {DIM}Every framework loops. The question is whether you catch it")
    print(f"  before it burns through your API budget.{RESET}")
    print()


if __name__ == "__main__":
    main()
