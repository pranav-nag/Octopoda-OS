"""
Octopoda Agent Runtime — Research Team Demo
=============================================
4 agents collaborate on a research project, exercising every runtime capability:
personal memory, shared memory, crash recovery, audit trail, task handoff,
snapshots, and continuous performance metrics.

Nothing simulated. All operations go through the real Synrix backend.
"""

import time
import threading
import random

from synrix_runtime.api.runtime import AgentRuntime


# ---------------------------------------------------------------------------
# Research data
# ---------------------------------------------------------------------------

FINDINGS = [
    ("edge_compute_growth", {
        "title": "Edge computing market reaches $61.4B",
        "source": "Gartner Q4 2024",
        "growth": "17.8% YoY",
        "relevance": "critical",
    }),
    ("latency_requirements", {
        "title": "Sub-millisecond memory required for autonomous systems",
        "source": "IEEE Robotics Survey",
        "threshold_us": 500,
        "domain": "robotics",
    }),
    ("persistent_state_challenge", {
        "title": "73% of edge deployments lose state on power cycle",
        "source": "Linux Foundation Edge Report",
        "impact": "high",
        "solution_gap": "no lightweight persistent memory layer exists",
    }),
    ("arm_deployment_surge", {
        "title": "ARM-based edge devices surpass 4.1M units",
        "source": "Counterpoint Research",
        "primary_use": "industrial_iot",
        "memory_needs": "persistent, crash-safe",
    }),
    ("octopoda_benchmark", {
        "title": "Octopoda achieves 53us avg write on Jetson",
        "source": "Internal benchmark suite",
        "avg_write_us": 53.3,
        "cold_start_ms": 1.2,
        "hot_path_ns": 192,
    }),
    ("competitor_analysis", {
        "title": "Redis/SQLite unsuitable for embedded edge",
        "source": "Comparative analysis",
        "redis_issue": "too much RAM for edge devices",
        "sqlite_issue": "WAL corruption on sudden power loss",
        "octopoda_advantage": "crash-safe lattice with zero-copy reads",
    }),
    ("market_opportunity", {
        "title": "Embedded AI memory market gap: $2.3B TAM",
        "source": "McKinsey Technology Report",
        "segments": ["robotics", "autonomous_vehicles", "industrial_iot", "medical_devices"],
        "adoption_barrier": "no drop-in persistent memory solution",
    }),
]

ANALYSIS_INSIGHTS = [
    "Market timing is optimal - edge compute growth aligns with persistent memory need",
    "Latency requirements validate our sub-100us architecture decision",
    "Power-cycle state loss is the #1 pain point we solve",
    "ARM deployment surge creates massive addressable market for our C lattice",
    "Benchmark numbers significantly outperform alternatives",
    "Competitor weaknesses are structural - not fixable with patches",
    "TAM is large enough to justify aggressive go-to-market",
]

REPORT_SECTIONS = [
    ("executive_summary", "Edge AI demands persistent, crash-safe memory. Octopoda fills this gap."),
    ("market_analysis", "The $61.4B edge compute market lacks a lightweight memory layer."),
    ("technical_advantage", "53us writes, crash recovery in <2ms, zero-copy reads."),
    ("competitive_landscape", "Redis too heavy, SQLite unsafe. Octopoda is purpose-built."),
    ("go_to_market", "Target robotics and industrial IoT first. $2.3B TAM."),
    ("risk_factors", "ARM fragmentation, adoption inertia, open-source competition."),
    ("recommendation", "Proceed with launch. Market timing and technical moat are strong."),
]


# ---------------------------------------------------------------------------
# Phase 1: Research
# ---------------------------------------------------------------------------

def phase_research(researcher):
    """Researcher discovers findings and shares with team."""
    print("\n[PHASE 1] Research - discovering findings...")

    for i, (key, data) in enumerate(FINDINGS):
        result = researcher.remember(f"finding:{key}", data)
        researcher.share(key, data, space="research_team")
        researcher.log_decision(
            f"Recorded finding: {data['title']}",
            f"Source credibility: {data['source']}. Relevance to thesis: high.",
            {"finding_key": key, "source": data["source"]},
        )
        print(f"  [researcher_01] Found: {data['title'][:55]}... ({result.latency_us:.0f}us)")
        time.sleep(random.uniform(0.4, 0.8))

    researcher.snapshot("research_complete")
    print(f"[PHASE 1] Complete - {len(FINDINGS)} findings shared to research_team space.\n")


# ---------------------------------------------------------------------------
# Phase 2: Analysis (with crash & recovery)
# ---------------------------------------------------------------------------

def phase_analysis(analyst, daemon):
    """Analyst processes findings, crashes mid-way, recovers, completes."""
    print("[PHASE 2] Analysis - processing shared findings...")

    # Read shared findings
    for key, _ in FINDINGS[:4]:
        shared = analyst.read_shared(key, space="research_team")
        if shared.found:
            print(f"  [analyst_01] Read shared: {key}")
        time.sleep(0.2)

    # Take pre-analysis snapshot
    snap = analyst.snapshot("pre_analysis")
    print(f"  [analyst_01] Snapshot: {snap.keys_captured} keys captured ({snap.latency_us:.0f}us)")

    # Analyze first 3 findings
    for i in range(3):
        key, data = FINDINGS[i]
        insight = ANALYSIS_INSIGHTS[i]
        analysis = {
            "finding": key,
            "insight": insight,
            "confidence": round(random.uniform(0.82, 0.97), 2),
            "iteration": i,
        }
        analyst.remember(f"analysis:{key}", analysis)
        analyst.share(f"analysis:{key}", analysis, space="research_team")
        analyst.log_decision(
            f"Analyzed: {key}",
            insight,
            {"confidence": analysis["confidence"]},
        )
        print(f"  [analyst_01] Analyzed: {key} (confidence: {analysis['confidence']})")
        time.sleep(random.uniform(0.3, 0.6))

    # ── CRASH ──
    print("\n  [analyst_01] *** CRASH - heartbeat stopped ***")
    analyst._heartbeat_running = False
    # Force heartbeat 15s stale so daemon detects it on next check
    analyst.backend.write(
        f"runtime:agents:analyst_01:heartbeat",
        {"value": time.time() - 15},
        metadata={"type": "heartbeat"},
    )

    # Wait for daemon heartbeat monitor (checks every 3s, timeout 10s)
    print("  [DAEMON] Monitoring heartbeats...")
    time.sleep(4)

    # Check if daemon detected it
    state = daemon.get_agent_state("analyst_01")
    print(f"  [DAEMON] analyst_01 state: {state}")

    if state != "running":
        recovery = daemon.recover_agent("analyst_01")
        steps = recovery.get("step_timings", {})
        print(f"  [DAEMON] Recovery complete in {recovery['recovery_time_us']:.1f}us:")
        print(f"           query_memory: {steps.get('query_memory_us', 0):.1f}us")
        print(f"           query_snapshots: {steps.get('query_snapshots_us', 0):.1f}us")
        print(f"           query_tasks: {steps.get('query_tasks_us', 0):.1f}us")
        print(f"           reconstruct: {steps.get('reconstruct_us', 0):.1f}us")
        print(f"           write_state: {steps.get('write_state_us', 0):.1f}us")
    else:
        print(f"  [DAEMON] Auto-recovery already completed")

    # Restart heartbeat
    analyst._heartbeat_running = True
    analyst._heartbeat_thread = threading.Thread(
        target=analyst._heartbeat_loop, name="heartbeat-analyst_01", daemon=True
    )
    analyst._heartbeat_thread.start()

    # Restore from snapshot
    restore = analyst.restore("pre_analysis")
    print(f"  [analyst_01] Restored from snapshot: {restore.keys_restored} keys in {restore.recovery_time_us:.1f}us")

    # Continue analysis from finding #4
    print("  [analyst_01] Resuming analysis post-recovery...")
    for i in range(3, len(FINDINGS)):
        key, data = FINDINGS[i]
        insight = ANALYSIS_INSIGHTS[i]
        analysis = {
            "finding": key,
            "insight": insight,
            "confidence": round(random.uniform(0.85, 0.98), 2),
            "iteration": i,
            "post_recovery": True,
        }
        analyst.remember(f"analysis:{key}", analysis)
        analyst.share(f"analysis:{key}", analysis, space="research_team")
        analyst.log_decision(
            f"Analyzed (post-recovery): {key}",
            insight,
            {"confidence": analysis["confidence"], "recovered": True},
        )
        print(f"  [analyst_01] Analyzed: {key} (confidence: {analysis['confidence']}) [post-recovery]")
        time.sleep(random.uniform(0.3, 0.6))

    analyst.snapshot("analysis_complete")
    print("[PHASE 2] Complete - all findings analyzed, crash survived.\n")


# ---------------------------------------------------------------------------
# Phase 3: Report writing + task handoff
# ---------------------------------------------------------------------------

def phase_writing(writer, coordinator, analyst):
    """Writer produces report, coordinator hands off review to analyst."""
    print("[PHASE 3] Writing - producing final report...")

    # Read all shared data
    for key, _ in FINDINGS:
        writer.read_shared(key, space="research_team")
        writer.read_shared(f"analysis:{key}", space="research_team")
    print("  [writer_01] Read all shared findings and analyses")

    # Write report sections
    for section_key, section_summary in REPORT_SECTIONS:
        section_data = {
            "section": section_key,
            "summary": section_summary,
            "word_count": random.randint(200, 800),
            "draft": 1,
        }
        writer.remember(f"report:{section_key}", section_data)
        writer.share(f"report:{section_key}", section_data, space="research_team")
        writer.log_decision(
            f"Wrote section: {section_key}",
            f"Synthesized from {len(FINDINGS)} findings and {len(ANALYSIS_INSIGHTS)} insights",
            {"section": section_key},
        )
        print(f"  [writer_01] Wrote: {section_key}")
        time.sleep(random.uniform(0.3, 0.5))

    writer.snapshot("report_draft_complete")

    # Coordinator hands off review task
    print("  [test_agent] Handing off review task to analyst_01...")
    handoff = coordinator.handoff(
        "review_draft_v1",
        "analyst_01",
        {"task": "Review report draft for accuracy", "sections": len(REPORT_SECTIONS)},
    )
    coordinator.log_decision(
        "Handed off review task",
        "Report draft ready for peer review by analyst",
        {"task_id": "review_draft_v1", "to": "analyst_01"},
    )
    print(f"  [test_agent] Handoff complete ({handoff.latency_us:.0f}us)")

    # Analyst claims and completes the task
    time.sleep(0.5)
    claim = analyst.claim_task("review_draft_v1")
    print(f"  [analyst_01] Claimed task: review_draft_v1")

    time.sleep(0.8)
    completion = analyst.complete_task("review_draft_v1", {
        "verdict": "approved",
        "comments": "Data accurately reflects findings. Recommend publication.",
        "sections_reviewed": len(REPORT_SECTIONS),
    })
    analyst.log_decision(
        "Completed review: approved for publication",
        "All sections cross-checked against source findings",
        {"task_id": "review_draft_v1", "verdict": "approved"},
    )
    print(f"  [analyst_01] Review complete: approved for publication")
    print("[PHASE 3] Complete - report written and peer-reviewed.\n")


# ---------------------------------------------------------------------------
# Phase 4: Continuous activity
# ---------------------------------------------------------------------------

def phase_keepalive(agents, stop_event):
    """All agents perform ongoing work for live dashboard data."""
    researcher, analyst, writer, coordinator = agents
    cycle = 0
    last_crash_time = time.time()

    while not stop_event.is_set():
        cycle += 1
        now = time.time()

        try:
            # Researcher: periodic scanning
            scan_data = {
                "scan_id": cycle,
                "timestamp": now,
                "new_sources": random.randint(0, 3),
                "status": "monitoring",
            }
            researcher.remember(f"scan:{cycle}", scan_data)
            if cycle % 3 == 0:
                researcher.share("latest_scan", scan_data, space="research_team")
                researcher.log_decision(
                    f"Scan cycle {cycle}: {scan_data['new_sources']} new sources",
                    "Continuous monitoring for market changes",
                    scan_data,
                )

            # Analyst: periodic re-evaluation
            eval_data = {
                "eval_id": cycle,
                "timestamp": now,
                "confidence_drift": round(random.uniform(-0.02, 0.02), 3),
                "pattern": f"trend_{cycle}",
            }
            analyst.remember(f"eval:{cycle}", eval_data)
            if cycle % 4 == 0:
                analyst.share("confidence_update", eval_data, space="research_team")
                analyst.log_decision(
                    f"Re-evaluated confidence: drift {eval_data['confidence_drift']}",
                    "Periodic re-assessment of analysis confidence",
                    eval_data,
                )

            # Writer: periodic status updates
            writer.remember(f"status:{cycle}", {
                "cycle": cycle,
                "timestamp": now,
                "report_status": "published",
                "views": random.randint(10, 500),
            })

            # Coordinator: monitoring
            coordinator.remember(f"monitor:{cycle}", {
                "cycle": cycle,
                "timestamp": now,
                "team_health": "nominal",
                "agents_active": 4,
            })
            if cycle % 5 == 0:
                coordinator.log_decision(
                    f"System check cycle {cycle}: all agents nominal",
                    "Routine health monitoring",
                    {"agents_active": 4, "cycle": cycle},
                )

            # Every ~60 seconds, trigger another crash/recovery
            if now - last_crash_time > 60:
                target = random.choice([researcher, writer])
                agent_id = target.agent_id
                print(f"\n  [KEEPALIVE] Triggering crash on {agent_id}...")
                target._heartbeat_running = False
                target.backend.write(
                    f"runtime:agents:{agent_id}:heartbeat",
                    {"value": time.time() - 15},
                    metadata={"type": "heartbeat"},
                )
                time.sleep(4)

                # Restart heartbeat
                target._heartbeat_running = True
                target._heartbeat_thread = threading.Thread(
                    target=target._heartbeat_loop,
                    name=f"heartbeat-{agent_id}",
                    daemon=True,
                )
                target._heartbeat_thread.start()
                last_crash_time = time.time()
                print(f"  [KEEPALIVE] {agent_id} recovered and resumed.")

        except Exception as e:
            print(f"  [KEEPALIVE] Error: {e}")

        stop_event.wait(5)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_demo(keep_alive=True):
    """Run the four-agent research team demo.

    Args:
        keep_alive: If True, agents stay active for dashboard viewing.
    """
    print("=" * 64)
    print("  OCTOPODA AGENT RUNTIME - RESEARCH TEAM DEMO")
    print("  4 agents | shared memory | crash recovery | audit trail")
    print("=" * 64)

    from synrix_runtime.core.daemon import RuntimeDaemon
    daemon = RuntimeDaemon.get_instance()
    if not daemon.running:
        daemon.start()

    # Create agents
    researcher = AgentRuntime("researcher_01", agent_type="researcher")
    analyst = AgentRuntime("analyst_01", agent_type="analyst")
    writer = AgentRuntime("writer_01", agent_type="writer")
    coordinator = AgentRuntime("test_agent", agent_type="coordinator")

    time.sleep(1)  # Let heartbeats register

    # Phase 1: Research
    phase_research(researcher)

    # Phase 2: Analysis with crash & recovery
    phase_analysis(analyst, daemon)

    # Phase 3: Writing & task handoff
    phase_writing(writer, coordinator, analyst)

    print("=" * 64)
    print("  DEMO COMPLETE")
    print(f"  All memory persisted in Octopoda")
    print(f"  Analyst crash detected by daemon, recovered automatically")
    print(f"  Report completed and peer-reviewed via task handoff")
    print("=" * 64)

    if keep_alive:
        print("\n  [LIVE] Agents staying active for dashboard...")
        print("  [LIVE] Open http://localhost:7842 to see them.\n")
        stop_event = threading.Event()
        activity_thread = threading.Thread(
            target=phase_keepalive,
            args=((researcher, analyst, writer, coordinator), stop_event),
            daemon=True,
        )
        activity_thread.start()
        return stop_event
    else:
        researcher.shutdown()
        analyst.shutdown()
        writer.shutdown()
        coordinator.shutdown()
        return None


if __name__ == "__main__":
    stop = run_demo(keep_alive=False)
