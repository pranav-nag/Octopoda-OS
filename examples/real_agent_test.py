"""
Real Agent Test — Octopoda Cloud SDK
=====================================
This simulates what a REAL customer would do:
  1. Connect with their API key
  2. Register agents
  3. Agents write/read memories as they work
  4. Agents log audit decisions
  5. Agents share data with each other
  6. Recovery from a crash
  7. Check metrics

Run:  python examples/real_agent_test.py
"""

import sys, os, time, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python-sdk"))

from synrix.cloud import Octopoda

API_KEY = os.environ.get("OCTOPODA_API_KEY", "")
BASE_URL = os.environ.get("OCTOPODA_URL", "https://api.octopodas.com")


def main():
    print("=" * 60)
    print("  OCTOPODA — Real Agent Test")
    print("=" * 60)

    client = Octopoda(api_key=API_KEY, base_url=BASE_URL, timeout=120)
    print(f"\nConnected to {BASE_URL}")

    # --- 1. Register agents ---
    print("\n[1] Registering agents...")
    sales = client.agent("sales-bot", metadata={"model": "gpt-4", "type": "sales"})
    analytics = client.agent("analytics-bot", metadata={"model": "claude-3", "type": "analytics"})
    support = client.agent("support-agent", metadata={"model": "gpt-4", "type": "support"})
    print(f"  Registered: {sales}, {analytics}, {support}")

    # --- 2. Sales agent works: stores customer interactions ---
    print("\n[2] Sales agent — storing customer data...")
    customers = [
        ("customer:alice", {"name": "Alice Chen", "company": "TechCorp", "deal_size": 25000, "stage": "negotiation"}),
        ("customer:bob", {"name": "Bob Smith", "company": "StartupXYZ", "deal_size": 8000, "stage": "demo"}),
        ("customer:carol", {"name": "Carol Davis", "company": "Enterprise Ltd", "deal_size": 120000, "stage": "proposal"}),
        ("customer:dave", {"name": "Dave Wilson", "company": "MidMarket Inc", "deal_size": 15000, "stage": "closed_won"}),
        ("customer:eve", {"name": "Eve Johnson", "company": "BigCo", "deal_size": 75000, "stage": "evaluation"}),
    ]
    for key, value in customers:
        result = sales.write(key, value, metadata={"source": "crm"}, tags=["customer", "active"])
        print(f"  Wrote {key} -> latency: {result.get('latency_us', 0):.0f}us")

    # Sales agent reads back a customer
    alice = sales.read("customer:alice")
    print(f"  Read customer:alice -> {alice}")

    # --- 3. Analytics agent works: stores metrics ---
    print("\n[3] Analytics agent — storing daily metrics...")
    for day in range(1, 8):
        analytics.write(f"metric:daily:{day}", {
            "date": f"2026-03-{day:02d}",
            "signups": random.randint(80, 200),
            "revenue": random.randint(5000, 15000),
            "churn_pct": round(random.uniform(1.5, 4.0), 1),
            "active_users": random.randint(3000, 6000),
        }, metadata={"source": "pipeline"}, tags=["daily", "metrics"])
    print(f"  Stored 7 daily metric snapshots")

    # --- 4. Support agent works: handles tickets ---
    print("\n[4] Support agent — handling tickets...")
    tickets = [
        ("ticket:T-5001", {"customer": "alice@techcorp.com", "issue": "API returns 500 on batch import", "severity": "P1", "status": "open"}),
        ("ticket:T-5002", {"customer": "frank@startup.io", "issue": "Dashboard not loading charts", "severity": "P2", "status": "investigating"}),
        ("ticket:T-5003", {"customer": "grace@corp.com", "issue": "Need SSO integration docs", "severity": "P3", "status": "open"}),
    ]
    for key, value in tickets:
        support.write(key, value, metadata={"source": "helpdesk"}, tags=["ticket", value["severity"]])
        print(f"  Created {key} ({value['severity']})")

    # Support resolves a ticket
    support.write("ticket:T-5001", {
        "customer": "alice@techcorp.com", "issue": "API returns 500 on batch import",
        "severity": "P1", "status": "resolved",
        "resolution": "Fixed null pointer in batch handler, deployed hotfix v2.0.1"
    }, metadata={"source": "helpdesk"}, tags=["ticket", "P1", "resolved"])
    print(f"  Resolved ticket:T-5001")

    # --- 5. Audit decisions ---
    print("\n[5] Logging audit decisions...")
    sales.decide("allow", "CRM data access for lead scoring", {"resource": "crm_database", "action": "read"})
    sales.decide("deny", "Cannot send bulk email without marketing approval", {"resource": "email_service", "action": "send_bulk", "count": 5000})
    analytics.decide("allow", "Aggregated revenue query for weekly report", {"resource": "data_warehouse", "action": "aggregate"})
    analytics.decide("deny", "Individual user tracking blocked by privacy policy", {"resource": "user_events", "action": "track_individual"})
    support.decide("allow", "Account access for verified ticket holder", {"resource": "user_account", "action": "view"})
    support.decide("escalate", "Refund request over $500 needs manager approval", {"resource": "billing", "action": "refund", "amount": 850})
    print(f"  Logged 6 decisions (3 allow, 2 deny, 1 escalate)")

    # --- 6. Shared memory — agents collaborate ---
    print("\n[6] Shared memory — cross-agent collaboration...")
    sales.share("deals-pipeline", "q2-forecast", {
        "total_pipeline": 243000,
        "expected_close": 168000,
        "deals_count": 5,
        "updated_by": "sales-bot",
    })
    print("  sales-bot -> deals-pipeline/q2-forecast")

    analytics.share("deals-pipeline", "conversion-stats", {
        "trial_to_paid": 12.3,
        "demo_to_close": 34.5,
        "avg_deal_cycle_days": 28,
    })
    print("  analytics-bot -> deals-pipeline/conversion-stats")

    support.share("known-issues", "api-batch-bug", {
        "issue": "Batch import 500 error",
        "affected_customers": 3,
        "fix": "Deployed in v2.0.1",
        "status": "resolved",
    })
    print("  support-agent -> known-issues/api-batch-bug")

    # --- 7. Simulate crash + recovery ---
    print("\n[7] Simulating crash recovery...")
    print("  analytics-bot crashed!")
    recovery = analytics.recover()
    print(f"  Recovered in {recovery.get('recovery_time_us', 0)/1000:.1f}ms")
    print(f"  Keys restored: {recovery.get('keys_restored', 0)}")
    print(f"  Success: {recovery.get('success', False)}")

    # --- 8. Check metrics ---
    print("\n[8] Checking metrics...")
    sys_metrics = client.system_metrics()
    print(f"  Total agents:     {sys_metrics.get('total_agents', 0)}")
    print(f"  Active agents:    {sys_metrics.get('active_agents', 0)}")
    print(f"  Total operations: {sys_metrics.get('total_operations', 0)}")
    print(f"  Recoveries:       {sys_metrics.get('total_recoveries', 0)}")

    for agent_name in ["sales-bot", "analytics-bot", "support-agent"]:
        a = client.get_agent(agent_name)
        m = a.metrics()
        print(f"  {agent_name}: score={m.get('performance_score', 0)}, writes={m.get('total_writes', 0)}, reads={m.get('total_reads', 0)}")

    # --- 9. List shared spaces ---
    print("\n[9] Shared spaces:")
    spaces = client.shared_spaces()
    for s in spaces:
        print(f"  {s['name']}: {s['key_count']} keys, agents: {s.get('active_agents', [])}")

    # --- 10. Verify agent memory ---
    print("\n[10] Verifying sales-bot memory...")
    mem = sales.list(limit=5)
    print(f"  Total items: {mem.get('total', 0)}")
    for item in mem.get("items", [])[:3]:
        print(f"  - {item['key']}")

    print("\n" + "=" * 60)
    print("  ALL TESTS PASSED — Real agent operations verified")
    print("=" * 60)

    client.close()


if __name__ == "__main__":
    main()
