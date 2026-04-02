"""
Synrix Agent Runtime — Multi-Crew Demo
========================================
Demonstrates multiple crews working simultaneously with isolated shared memory.
"""

import time
import threading

from synrix_runtime.api.runtime import AgentRuntime
from synrix_runtime.core.daemon import RuntimeDaemon


def crew_research(crew_name, topic, findings):
    """A research crew working on a topic."""
    researcher = AgentRuntime(f"{crew_name}_researcher", agent_type="researcher")
    analyst = AgentRuntime(f"{crew_name}_analyst", agent_type="analyst")

    print(f"\n[{crew_name}] Starting research on: {topic}")

    # Researcher gathers
    for key, value in findings:
        result = researcher.remember(key, value)
        researcher.share(key, value, space=crew_name)
        print(f"  [{crew_name}/researcher] Stored: {key} ({result.latency_us:.1f}us)")
        time.sleep(0.2)

    researcher.snapshot(f"{crew_name}_research_done")

    # Analyst processes
    time.sleep(0.5)
    for key, value in findings:
        analysis = {"finding": key, "assessment": "significant", "crew": crew_name}
        analyst.remember(f"analysis:{key}", analysis)
        analyst.share(f"analysis:{key}", analysis, space=crew_name)
        analyst.log_decision(f"Analysed {key}", f"Relevant to {topic}", analysis)
        print(f"  [{crew_name}/analyst] Analysed: {key}")
        time.sleep(0.15)

    analyst.snapshot(f"{crew_name}_analysis_done")
    print(f"[{crew_name}] Crew complete.\n")

    researcher.shutdown()
    analyst.shutdown()


def run_demo():
    print("=" * 60)
    print("  SYNRIX AGENT RUNTIME  -  MULTI-CREW DEMO")
    print("=" * 60)

    daemon = RuntimeDaemon.get_instance()
    if not daemon.running:
        daemon.start()

    # Two crews working in parallel on different topics
    crew_a_findings = [
        ("quantum_compute", {"area": "quantum", "status": "emerging"}),
        ("quantum_error_rates", {"value": "0.1%", "improving": True}),
        ("quantum_memory", {"type": "topological", "stability": "high"}),
    ]

    crew_b_findings = [
        ("bio_sensors", {"area": "biotech", "type": "neural_interface"}),
        ("bio_latency", {"value": "sub_ms", "target": "real_time"}),
        ("bio_applications", {"domain": "prosthetics", "market": "$2.1B"}),
    ]

    t1 = threading.Thread(target=crew_research, args=("crew_quantum", "Quantum Computing", crew_a_findings))
    t2 = threading.Thread(target=crew_research, args=("crew_biotech", "Biotech Sensors", crew_b_findings))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Cross-crew coordinator reads from both
    coordinator = AgentRuntime("coordinator_01", agent_type="planner")
    print("[COORDINATOR] Reading from both crews...")

    quantum_data = coordinator.search("", limit=50)
    for item in quantum_data.items[:3]:
        print(f"  [COORDINATOR] Found: {item.get('key')}")

    summary = {
        "crews_coordinated": 2,
        "total_findings": len(crew_a_findings) + len(crew_b_findings),
        "shared_spaces": ["crew_quantum", "crew_biotech"],
        "completed_at": time.time(),
    }
    coordinator.remember("coordination_summary", summary)
    coordinator.log_decision("Coordination complete", "Both crews delivered findings", summary)
    coordinator.snapshot("coordination_done")

    print(f"\n[COORDINATOR] Summary: {summary['crews_coordinated']} crews, {summary['total_findings']} findings")

    coordinator.shutdown()

    print("\n" + "=" * 60)
    print("  MULTI-CREW DEMO COMPLETE")
    print(f"  Both crews ran in parallel with isolated shared memory")
    print("=" * 60)


if __name__ == "__main__":
    run_demo()
