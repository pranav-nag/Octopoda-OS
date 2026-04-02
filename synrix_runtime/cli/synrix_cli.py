"""
Synrix Agent Runtime — CLI
Command line interface for managing the runtime.

Usage:
    python -m synrix_runtime.cli.synrix_cli status
    python -m synrix_runtime.cli.synrix_cli agents list
    python -m synrix_runtime.cli.synrix_cli demo run
"""

import argparse
import json
import time


def get_backend():
    from synrix.agent_backend import get_synrix_backend
    from synrix_runtime.config import SynrixConfig
    config = SynrixConfig.from_env()
    return get_synrix_backend(**config.get_backend_kwargs())


def ensure_daemon():
    from synrix_runtime.core.daemon import RuntimeDaemon
    daemon = RuntimeDaemon.get_instance()
    if not daemon.running:
        daemon.start()
    return daemon


def cmd_status(args):
    """Show system status."""
    daemon = ensure_daemon()
    status = daemon.get_system_status()

    print("\n  SYNRIX AGENT RUNTIME STATUS")
    print("  " + "-" * 40)
    print(f"  Status:           {status['status']}")
    print(f"  Version:          {status['version']}")
    print(f"  Uptime:           {format_uptime(status['uptime_seconds'])}")
    print(f"  Active Agents:    {status['active_agents']}")
    print(f"  Total Agents:     {status['total_agents']}")
    print(f"  Total Operations: {status['total_operations']}")
    print(f"  Daemon Threads:   {status['daemon_threads']}")
    print()


def cmd_agents_list(args):
    """List all agents."""
    daemon = ensure_daemon()
    agents = daemon.get_active_agents()

    if not agents:
        print("\n  No agents registered.\n")
        return

    from synrix_runtime.monitoring.metrics import MetricsCollector
    collector = MetricsCollector.get_instance(daemon.backend)

    print(f"\n  {'AGENT ID':<20s} {'TYPE':<12s} {'STATE':<12s} {'SCORE':>7s} {'MEMORY':>7s} {'OPS':>7s} {'CRASHES':>8s}")
    print("  " + "-" * 85)

    for agent in agents:
        agent_id = agent.get("agent_id", "?")
        try:
            m = collector.get_agent_metrics(agent_id)
            score = f"{m.performance_score:.0f}"
            memory = str(m.memory_node_count)
            ops = str(m.total_operations)
            crashes = str(m.crash_count)
        except Exception:
            score = "-"
            memory = "-"
            ops = "-"
            crashes = "-"

        print(f"  {agent_id:<20s} {agent.get('type', 'generic'):<12s} {agent.get('state', '?'):<12s} {score:>7s} {memory:>7s} {ops:>7s} {crashes:>8s}")
    print()


def cmd_agents_inspect(args):
    """Inspect a single agent."""
    daemon = ensure_daemon()
    agent_id = args.agent_id

    from synrix_runtime.monitoring.metrics import MetricsCollector
    collector = MetricsCollector.get_instance(daemon.backend)
    m = collector.get_agent_metrics(agent_id)
    breakdown = collector.get_performance_breakdown(agent_id)

    print(f"\n  AGENT: {agent_id}")
    print("  " + "-" * 40)
    print(f"  Total Operations:  {m.total_operations}")
    print(f"  Writes:            {m.total_writes}")
    print(f"  Reads:             {m.total_reads}")
    print(f"  Queries:           {m.total_queries}")
    print(f"  Avg Write Latency: {m.avg_write_latency_us:.1f}us")
    print(f"  Avg Read Latency:  {m.avg_read_latency_us:.1f}us")
    print(f"  Error Rate:        {m.error_rate:.2%}")
    print(f"  Crash Count:       {m.crash_count}")
    print(f"  Recovery Count:    {m.recovery_count}")
    print(f"  Memory Nodes:      {m.memory_node_count}")
    print(f"  Performance Score: {m.performance_score:.1f}/100")
    print(f"  Uptime:            {format_uptime(m.uptime_seconds)}")

    print(f"\n  Score Breakdown:")
    for comp_name, comp in breakdown.items():
        if isinstance(comp, dict) and "score" in comp:
            print(f"    {comp_name:<30s} {comp['score']:.1f}/{comp['max']}")
    print()


def cmd_memory_browse(args):
    """Browse agent memory."""
    backend = get_backend()
    prefix = f"agents:{args.agent_id}:" if args.agent_id else ""

    start = time.perf_counter_ns()
    results = backend.query_prefix(prefix, limit=50)
    latency_us = (time.perf_counter_ns() - start) / 1000

    print(f"\n  Memory Browser: {prefix or '(all)'} ({latency_us:.1f}us)")
    print("  " + "-" * 60)

    for r in results:
        key = r.get("key", "")
        data = r.get("data", {})
        val = data.get("value", data)
        val_str = json.dumps(val) if isinstance(val, (dict, list)) else str(val)
        if len(val_str) > 60:
            val_str = val_str[:57] + "..."
        print(f"  {key:<40s} {val_str}")
    print(f"\n  {len(results)} keys found.\n")


def cmd_memory_search(args):
    """Search memory by prefix."""
    backend = get_backend()
    prefix = args.prefix

    start = time.perf_counter_ns()
    results = backend.query_prefix(prefix, limit=100)
    latency_us = (time.perf_counter_ns() - start) / 1000

    print(f"\n  Search: '{prefix}' ({len(results)} results, {latency_us:.1f}us)")
    print("  " + "-" * 60)

    for r in results:
        key = r.get("key", "")
        print(f"  {key}")
    print()


def cmd_audit_replay(args):
    """Replay audit events for an agent."""
    from synrix_runtime.monitoring.audit import AuditSystem
    backend = get_backend()
    audit = AuditSystem(backend)

    minutes = args.minutes or 30
    now = time.time()
    events = audit.replay(args.agent_id, from_ts=now - (minutes * 60), to_ts=now)

    print(f"\n  Audit Replay: {args.agent_id} (last {minutes} minutes)")
    print("  " + "-" * 60)

    for event in events:
        ts = event.get("timestamp", 0)
        ts_str = time.strftime("%H:%M:%S", time.localtime(ts)) if ts else "?"
        etype = event.get("event_type", "?")
        summary = event.get("decision", event.get("reason", json.dumps(event)[:60]))
        print(f"  [{ts_str}] {etype.upper():<12s} {summary}")
    print(f"\n  {len(events)} events.\n")


def cmd_audit_explain(args):
    """Explain a specific decision."""
    from synrix_runtime.monitoring.audit import AuditSystem
    backend = get_backend()
    audit = AuditSystem(backend)

    result = audit.explain_decision(args.agent_id, float(args.timestamp))

    print(f"\n  Decision Explanation: {args.agent_id}")
    print("  " + "-" * 60)

    decided = result.get("what_it_decided", {})
    print(f"  Decision:  {decided.get('decision', '?')}")
    print(f"  Reasoning: {decided.get('reasoning', '?')}")
    print(f"  Queried:   {len(result.get('what_it_queried', []))} read ops before")
    print(f"  Wrote:     {len(result.get('what_it_wrote', []))} write ops after")
    print(f"  Knew:      {len(result.get('what_agent_knew', {}))} memory keys")
    print()


def cmd_recovery_history(args):
    """Show recovery history."""
    from synrix_runtime.core.recovery import RecoveryOrchestrator
    backend = get_backend()
    orchestrator = RecoveryOrchestrator(backend)
    stats = orchestrator.get_recovery_stats()
    history = orchestrator.get_all_recovery_history()

    print("\n  RECOVERY HISTORY")
    print("  " + "-" * 50)
    print(f"  Total Recoveries:    {stats['total_recoveries']}")
    print(f"  Mean Recovery Time:  {stats['mean_recovery_time_us']:.1f}us")
    print(f"  Fastest Recovery:    {stats['fastest_recovery_us']:.1f}us")
    print(f"  Slowest Recovery:    {stats['slowest_recovery_us']:.1f}us")
    print(f"  Zero Data Loss Rate: {stats['zero_data_loss_rate']:.1f}%")

    if history:
        print(f"\n  Recent Events:")
        for event in history[:10]:
            if isinstance(event, dict):
                aid = event.get("agent_id", "?")
                rt = event.get("recovery_time_us", 0)
                keys = event.get("keys_restored", 0)
                print(f"    {aid:<20s} {rt:.1f}us  {keys} keys restored")
    print()


def cmd_demo_run(args):
    """Run the three-agent demo."""
    from synrix_runtime.demo.three_agent_demo import run_demo
    run_demo()


def cmd_demo_crash(args):
    """Crash an agent."""
    from synrix_runtime.api.system_calls import SystemCalls
    backend = get_backend()
    ensure_daemon()
    syscalls = SystemCalls(backend)
    result = syscalls.simulate_crash(args.agent_id)
    print(f"\n  Agent {args.agent_id} crashed: {result}")

    result = syscalls.trigger_recovery(args.agent_id)
    print(f"  Recovery: {result['recovery_time_us']:.1f}us, {result['keys_restored']} keys\n")


def cmd_dashboard(args):
    """Start the web dashboard."""
    from synrix_runtime.dashboard.app import run_dashboard
    ensure_daemon()
    port = args.port or 7842
    print(f"\n  Starting dashboard on http://localhost:{port}")
    import webbrowser
    webbrowser.open(f"http://localhost:{port}")
    run_dashboard(port=port)


def cmd_export(args):
    """Export agent state."""
    from synrix_runtime.api.system_calls import SystemCalls
    backend = get_backend()
    syscalls = SystemCalls(backend)
    data = syscalls.export_agent_state(args.agent_id)

    filename = f"{args.agent_id}_export.json"
    with open(filename, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"\n  Exported {data['memory_keys']} keys to {filename}\n")


def format_uptime(seconds):
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{int(seconds//60)}m {int(seconds%60)}s"
    return f"{int(seconds//3600)}h {int((seconds%3600)//60)}m"


def main():
    parser = argparse.ArgumentParser(
        prog="synrix-runtime",
        description="Synrix Agent Runtime CLI"
    )
    subparsers = parser.add_subparsers(dest="command")

    # status
    subparsers.add_parser("status", help="Show system status")

    # agents
    agents_parser = subparsers.add_parser("agents", help="Agent management")
    agents_sub = agents_parser.add_subparsers(dest="agents_command")
    agents_sub.add_parser("list", help="List all agents")
    inspect_parser = agents_sub.add_parser("inspect", help="Inspect an agent")
    inspect_parser.add_argument("agent_id", help="Agent ID to inspect")

    # memory
    memory_parser = subparsers.add_parser("memory", help="Memory operations")
    memory_sub = memory_parser.add_subparsers(dest="memory_command")
    browse_parser = memory_sub.add_parser("browse", help="Browse agent memory")
    browse_parser.add_argument("agent_id", nargs="?", default="", help="Agent ID")
    search_parser = memory_sub.add_parser("search", help="Search memory")
    search_parser.add_argument("prefix", help="Prefix to search")

    # audit
    audit_parser = subparsers.add_parser("audit", help="Audit operations")
    audit_sub = audit_parser.add_subparsers(dest="audit_command")
    replay_parser = audit_sub.add_parser("replay", help="Replay agent audit")
    replay_parser.add_argument("agent_id", help="Agent ID")
    replay_parser.add_argument("--minutes", type=int, default=30, help="Minutes to replay")
    explain_parser = audit_sub.add_parser("explain", help="Explain a decision")
    explain_parser.add_argument("agent_id", help="Agent ID")
    explain_parser.add_argument("timestamp", help="Decision timestamp")

    # recovery
    recovery_parser = subparsers.add_parser("recovery", help="Recovery operations")
    recovery_sub = recovery_parser.add_subparsers(dest="recovery_command")
    recovery_sub.add_parser("history", help="Show recovery history")

    # demo
    demo_parser = subparsers.add_parser("demo", help="Demo operations")
    demo_sub = demo_parser.add_subparsers(dest="demo_command")
    demo_sub.add_parser("run", help="Run the three-agent demo")
    crash_parser = demo_sub.add_parser("crash", help="Crash an agent")
    crash_parser.add_argument("agent_id", help="Agent ID to crash")

    # dashboard
    dash_parser = subparsers.add_parser("dashboard", help="Start web dashboard")
    dash_parser.add_argument("--port", type=int, default=7842, help="Dashboard port")

    # export
    export_parser = subparsers.add_parser("export", help="Export agent state")
    export_parser.add_argument("agent_id", help="Agent ID to export")
    export_parser.add_argument("--format", choices=["json"], default="json", help="Export format")

    args = parser.parse_args()

    commands = {
        "status": cmd_status,
        "dashboard": cmd_dashboard,
    }

    if args.command == "agents":
        if args.agents_command == "list":
            cmd_agents_list(args)
        elif args.agents_command == "inspect":
            cmd_agents_inspect(args)
        else:
            agents_parser.print_help()
    elif args.command == "memory":
        if args.memory_command == "browse":
            cmd_memory_browse(args)
        elif args.memory_command == "search":
            cmd_memory_search(args)
        else:
            memory_parser.print_help()
    elif args.command == "audit":
        if args.audit_command == "replay":
            cmd_audit_replay(args)
        elif args.audit_command == "explain":
            cmd_audit_explain(args)
        else:
            audit_parser.print_help()
    elif args.command == "recovery":
        if args.recovery_command == "history":
            cmd_recovery_history(args)
        else:
            recovery_parser.print_help()
    elif args.command == "demo":
        if args.demo_command == "run":
            cmd_demo_run(args)
        elif args.demo_command == "crash":
            cmd_demo_crash(args)
        else:
            demo_parser.print_help()
    elif args.command in commands:
        commands[args.command](args)
    elif args.command == "export":
        cmd_export(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
