"""
Continuous Agent Workload — simulates real agents running over time.
Each agent does realistic work in a loop: writes, reads, decisions, shares.
"""

import sys, os, time, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python-sdk"))

from synrix.cloud import Octopoda

API_KEY = os.environ.get("OCTOPODA_API_KEY", "")
BASE_URL = os.environ.get("OCTOPODA_URL", "https://api.octopodas.com")


def run_sales_cycle(agent, cycle):
    """Sales bot processes a new lead."""
    companies = ["Acme Corp", "TechStart", "MegaInc", "DataFlow", "CloudNine", "PixelForge", "NeuralNet", "ByteWorks"]
    company = random.choice(companies)
    deal = random.randint(5000, 100000)

    # Write lead
    agent.write(f"lead:cycle{cycle}:{company.lower().replace(' ', '-')}", {
        "company": company,
        "contact": f"buyer@{company.lower().replace(' ', '')}.com",
        "deal_size": deal,
        "stage": random.choice(["discovery", "demo", "proposal", "negotiation"]),
        "source": random.choice(["inbound", "referral", "webinar", "cold-outreach"]),
    }, tags=["lead", "active"])

    # Read back to verify
    agent.read(f"lead:cycle{cycle}:{company.lower().replace(' ', '-')}")

    # Decision: should we offer a discount?
    if deal > 50000:
        agent.decide("allow", f"Enterprise discount approved for {company} ({deal})",
                     {"resource": "pricing", "action": "apply_discount", "amount": deal * 0.1})
    else:
        agent.decide("deny", f"Standard pricing for {company} - deal too small for discount",
                     {"resource": "pricing", "action": "apply_discount"})

    return company, deal


def run_analytics_cycle(agent, cycle):
    """Analytics bot processes daily metrics."""
    signups = random.randint(50, 300)
    revenue = random.randint(3000, 20000)
    churn = round(random.uniform(1.0, 5.0), 1)

    agent.write(f"report:cycle{cycle}:daily", {
        "signups": signups,
        "revenue": revenue,
        "churn_pct": churn,
        "active_users": random.randint(2000, 8000),
        "top_feature": random.choice(["search", "dashboard", "api", "integrations", "export"]),
    }, tags=["report", "daily"])

    # Anomaly detection decision
    if churn > 4.0:
        agent.decide("escalate", f"Churn spike detected: {churn}% (threshold: 4.0%)",
                     {"resource": "alerts", "action": "notify_team", "metric": "churn"})
    elif signups > 200:
        agent.decide("allow", f"High signup day ({signups}) - scaling resources",
                     {"resource": "infrastructure", "action": "auto_scale"})
    else:
        agent.decide("allow", f"Normal metrics day - no action needed",
                     {"resource": "monitoring", "action": "log"})

    return signups, revenue


def run_support_cycle(agent, cycle):
    """Support bot handles a new ticket."""
    issues = [
        "API returning 500 on large payloads",
        "Dashboard charts not loading in Safari",
        "Rate limit too aggressive for batch operations",
        "SSO login redirect failing",
        "Export CSV timeout on large datasets",
        "Webhook delivery delays",
        "Memory search returning stale results",
    ]
    issue = random.choice(issues)
    severity = random.choice(["P1", "P2", "P2", "P3", "P3"])

    agent.write(f"ticket:cycle{cycle}:T-{6000+cycle}", {
        "issue": issue,
        "severity": severity,
        "customer": f"user{random.randint(100,999)}@company.com",
        "status": "open",
    }, tags=["ticket", severity])

    # Resolve immediately if P3
    if severity == "P3":
        agent.write(f"ticket:cycle{cycle}:T-{6000+cycle}", {
            "issue": issue,
            "severity": severity,
            "status": "resolved",
            "resolution": "Directed to knowledge base article",
        }, tags=["ticket", severity, "resolved"])
        agent.decide("allow", f"Auto-resolved P3 ticket with KB article",
                     {"resource": "knowledge_base", "action": "suggest_article"})
    elif severity == "P1":
        agent.decide("escalate", f"P1 ticket requires immediate engineering attention: {issue}",
                     {"resource": "engineering", "action": "page_oncall"})

    return issue, severity


def main():
    print("=" * 60)
    print("  OCTOPODA — Continuous Agent Workload")
    print("=" * 60)

    client = Octopoda(api_key=API_KEY, base_url=BASE_URL)

    sales = client.agent("sales-bot", metadata={"model": "gpt-4", "type": "sales"})
    analytics = client.agent("analytics-bot", metadata={"model": "claude-3", "type": "analytics"})
    support = client.agent("support-agent", metadata={"model": "gpt-4", "type": "support"})

    print(f"\nRunning 20 cycles against {BASE_URL}...\n")

    total_ops = 0

    for cycle in range(1, 21):
        # Sales bot works
        company, deal = run_sales_cycle(sales, cycle)
        total_ops += 3  # write + read + decide

        # Analytics bot works
        signups, revenue = run_analytics_cycle(analytics, cycle)
        total_ops += 2  # write + decide

        # Support bot works
        issue, sev = run_support_cycle(support, cycle)
        total_ops += 2  # write + decide (+ extra write if resolved)

        # Every 5 cycles, agents share data with each other
        if cycle % 5 == 0:
            sales.share("pipeline-sync", f"update-{cycle}", {
                "total_leads": cycle * 2,
                "pipeline_value": random.randint(100000, 500000),
            })
            analytics.share("pipeline-sync", f"metrics-{cycle}", {
                "conversion_rate": round(random.uniform(8, 18), 1),
                "avg_deal_size": random.randint(10000, 50000),
            })
            support.share("known-issues", f"status-{cycle}", {
                "open_p1": random.randint(0, 3),
                "resolved_today": random.randint(5, 15),
            })
            total_ops += 3
            print(f"  Cycle {cycle:2d}: {company} (${deal:,}) | {signups} signups | {sev} ticket | + shared memory sync")
        else:
            print(f"  Cycle {cycle:2d}: {company} (${deal:,}) | {signups} signups | {sev} ticket: {issue[:40]}")

        # Small delay to simulate real timing
        time.sleep(0.2)

    # Final summary
    print(f"\n--- Completed {total_ops}+ operations across 20 cycles ---\n")

    metrics = client.system_metrics()
    print(f"System metrics:")
    print(f"  Total agents:     {metrics.get('total_agents')}")
    print(f"  Active agents:    {metrics.get('active_agents')}")
    print(f"  Total operations: {metrics.get('total_operations')}")
    print(f"  Recoveries:       {metrics.get('total_recoveries')}")

    print(f"\nAgent scores:")
    for name in ["sales-bot", "analytics-bot", "support-agent"]:
        m = client.get_agent(name).metrics()
        print(f"  {name}: score={m.get('performance_score')}, writes={m.get('total_writes')}, reads={m.get('total_reads')}, ops={m.get('total_operations')}")

    print(f"\nShared spaces:")
    for s in client.shared_spaces():
        print(f"  {s['name']}: {s['key_count']} keys, agents: {s.get('active_agents', [])}")

    print(f"\n{'=' * 60}")
    print(f"  WORKLOAD COMPLETE")
    print(f"{'=' * 60}")

    client.close()


if __name__ == "__main__":
    main()
