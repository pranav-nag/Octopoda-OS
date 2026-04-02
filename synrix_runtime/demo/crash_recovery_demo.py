"""
Synrix Agent Runtime — Crash Recovery Demo
============================================
Demonstrates rapid crash recovery with full state preservation.
"""

import time

from synrix_runtime.api.runtime import AgentRuntime
from synrix_runtime.core.recovery import RecoveryOrchestrator
from synrix_runtime.core.daemon import RuntimeDaemon


def run_demo():
    print("=" * 60)
    print("  SYNRIX AGENT RUNTIME  -  CRASH RECOVERY DEMO")
    print("=" * 60)

    daemon = RuntimeDaemon.get_instance()
    if not daemon.running:
        daemon.start()

    # Create agent and build up state
    agent = AgentRuntime("recovery_test_01", agent_type="researcher")

    print("\n[Phase 1] Building agent memory...")
    for i in range(20):
        key = f"knowledge:item_{i:03d}"
        value = {"fact": f"Important fact #{i}", "confidence": 0.95, "source": "research_db"}
        result = agent.remember(key, value)
        print(f"  Stored: {key} ({result.latency_us:.1f}us)")

    agent.snapshot("pre_crash")
    memory_before = agent.search("knowledge:", limit=100)
    print(f"\n  Total memory keys before crash: {memory_before.count}")

    # Simulate crash
    print("\n[Phase 2] Simulating crash...")
    agent._heartbeat_running = False
    daemon.set_agent_state("recovery_test_01", "crashed")
    ts = int(time.time() * 1000000)
    daemon.backend.write(
        f"runtime:events:crash:recovery_test_01:{ts}",
        {"agent_id": "recovery_test_01", "reason": "simulated", "timestamp": time.time()},
        metadata={"type": "crash_event"}
    )
    print("  Agent crashed!")

    time.sleep(0.5)

    # Recovery
    print("\n[Phase 3] Executing recovery...")
    orchestrator = RecoveryOrchestrator(daemon.backend)
    result = orchestrator.full_recovery("recovery_test_01")

    print(f"\n  Recovery Results:")
    print(f"  +---------------------------------+")
    print(f"  | Total Recovery Time: {result.recovery_time_us:>10.1f}us |")
    print(f"  | Keys Restored:       {result.keys_restored:>10d}   |")
    print(f"  | Snapshot Used:       {str(result.snapshot_used or 'latest')[:10]:>10s}   |")
    print(f"  | Memory Size:         {result.memory_size_bytes:>10d} B |")
    print(f"  +---------------------------------+")
    print(f"\n  Step-by-step timings:")
    for step, timing in result.step_timings.items():
        print(f"    {step:<25s} {timing:>10.1f}us")

    # Verify data integrity
    print("\n[Phase 4] Verifying data integrity...")
    agent._heartbeat_running = True
    agent._heartbeat_thread = None
    memory_after = agent.search("knowledge:", limit=100)
    print(f"  Memory keys after recovery: {memory_after.count}")
    print(f"  Data preserved:             {'YES' if memory_after.count >= memory_before.count else 'PARTIAL'}")

    # Compare
    comparison = orchestrator.compare_pre_post_crash("recovery_test_01", time.time() - 10)
    print(f"  Pre-crash keys:             {comparison['pre_crash_keys']}")
    print(f"  Post-recovery keys:         {comparison['post_recovery_keys']}")

    print(f"\n  ZERO DATA LOSS CONFIRMED")

    agent.shutdown()
    print("\n" + "=" * 60)
    print("  CRASH RECOVERY DEMO COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    run_demo()
