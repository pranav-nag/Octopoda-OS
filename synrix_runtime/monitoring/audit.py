"""
Synrix Agent Runtime — Audit System
Complete decision audit trail with full memory snapshots.
"""

import time
import json
from typing import Dict, List, Optional


class AuditSystem:
    """Full audit trail for agent decisions, handoffs, and anomalies."""

    def __init__(self, backend=None):
        self.backend = backend
        if self.backend is None:
            from synrix.agent_backend import get_synrix_backend
            from synrix_runtime.config import SynrixConfig
            config = SynrixConfig.from_env()
            self.backend = get_synrix_backend(**config.get_backend_kwargs())

    def log_decision(self, agent_id: str, decision: str, reasoning: str, memory_snapshot: dict = None):
        """Log an agent decision with full memory context."""
        ts = int(time.time() * 1000000)
        if memory_snapshot is None:
            memory_snapshot = self._capture_snapshot(agent_id)

        entry = {
            "event_type": "decision",
            "agent_id": agent_id,
            "decision": decision,
            "reasoning": reasoning,
            "memory_snapshot": memory_snapshot,
            "timestamp": time.time(),
        }
        self.backend.write(
            f"audit:{agent_id}:{ts}:decision",
            entry,
            metadata={"type": "audit_decision", "agent_id": agent_id}
        )

    def log_handoff(self, from_agent: str, to_agent: str, task_id: str, payload: dict, shared_context: dict = None):
        """Log a task handoff between agents."""
        ts = int(time.time() * 1000000)
        entry = {
            "event_type": "handoff",
            "from_agent": from_agent,
            "to_agent": to_agent,
            "task_id": task_id,
            "payload": payload,
            "shared_context": shared_context or {},
            "timestamp": time.time(),
        }
        self.backend.write(
            f"audit:handoffs:{task_id}:{ts}",
            entry,
            metadata={"type": "audit_handoff"}
        )

    def log_anomaly(self, agent_id: str, anomaly_type: str, details: dict):
        """Log an anomaly event."""
        ts = int(time.time() * 1000000)
        entry = {
            "event_type": "anomaly",
            "agent_id": agent_id,
            "anomaly_type": anomaly_type,
            "details": details,
            "timestamp": time.time(),
        }
        self.backend.write(
            f"audit:{agent_id}:{ts}:anomaly",
            entry,
            metadata={"type": "audit_anomaly", "agent_id": agent_id}
        )

    def log_crash(self, agent_id: str, reason: str, context: dict = None):
        """Log a crash event."""
        ts = int(time.time() * 1000000)
        entry = {
            "event_type": "crash",
            "agent_id": agent_id,
            "reason": reason,
            "context": context or {},
            "memory_snapshot": self._capture_snapshot(agent_id),
            "timestamp": time.time(),
        }
        self.backend.write(
            f"audit:{agent_id}:{ts}:crash",
            entry,
            metadata={"type": "audit_crash", "agent_id": agent_id}
        )

    def log_recovery(self, agent_id: str, recovery_result: dict):
        """Log a recovery event."""
        ts = int(time.time() * 1000000)
        entry = {
            "event_type": "recovery",
            "agent_id": agent_id,
            "recovery_result": recovery_result,
            "timestamp": time.time(),
        }
        self.backend.write(
            f"audit:{agent_id}:{ts}:recovery",
            entry,
            metadata={"type": "audit_recovery", "agent_id": agent_id}
        )

    def replay(self, agent_id: str, from_ts: float = None, to_ts: float = None) -> list:
        """Replay all audit events for an agent in chronological order."""
        results = self.backend.query_prefix(f"audit:{agent_id}:", limit=500)
        events = []
        for r in results:
            data = r.get("data", {})
            val = data.get("value", data)
            if isinstance(val, dict):
                ts = val.get("timestamp", 0)
                if from_ts and ts < from_ts:
                    continue
                if to_ts and ts > to_ts:
                    continue
                val["_key"] = r.get("key", "")
                events.append(val)

        events.sort(key=lambda x: x.get("timestamp", 0))
        return events

    def explain_decision(self, agent_id: str, decision_timestamp: float) -> dict:
        """Explain a specific decision with full causal context."""
        # Find the decision
        ts_us = int(decision_timestamp * 1000000) if decision_timestamp < 1e12 else int(decision_timestamp)
        all_events = self.replay(agent_id)

        decision_event = None
        for e in all_events:
            is_decision = e.get("event_type") == "decision" or "decision" in e or ":decision" in e.get("_key", "")
            if is_decision:
                e_ts = e.get("timestamp", 0)
                if abs(e_ts - decision_timestamp) < 5:
                    decision_event = e
                    break

        if decision_event is None:
            # Try approximate match
            decisions = [e for e in all_events if e.get("event_type") == "decision" or "decision" in e or ":decision" in e.get("_key", "")]
            if decisions:
                decision_event = min(decisions, key=lambda x: abs(x.get("timestamp", 0) - decision_timestamp))

        if decision_event is None:
            return {"error": "Decision not found", "agent_id": agent_id}

        d_ts = decision_event.get("timestamp", 0)

        # What the agent queried (reads in 30s before decision)
        reads_before = []
        writes_after = []
        for e in all_events:
            e_ts = e.get("timestamp", 0)
            if e_ts >= d_ts - 30 and e_ts <= d_ts and e.get("event_type") in ("decision",):
                reads_before.append(e)
            if e_ts > d_ts and e_ts <= d_ts + 30:
                writes_after.append(e)

        # Get read metrics around decision time
        read_metrics = self.backend.query_prefix(f"metrics:{agent_id}:read:", limit=100)
        reads_near = []
        for r in read_metrics:
            data = r.get("data", {})
            val = data.get("value", data)
            if isinstance(val, dict):
                ts = val.get("timestamp", 0)
                if d_ts - 30 <= ts <= d_ts:
                    reads_near.append(val)

        write_metrics = self.backend.query_prefix(f"metrics:{agent_id}:write:", limit=100)
        writes_near = []
        for w in write_metrics:
            data = w.get("data", {})
            val = data.get("value", data)
            if isinstance(val, dict):
                ts = val.get("timestamp", 0)
                if d_ts < ts <= d_ts + 30:
                    writes_near.append(val)

        return {
            "agent_id": agent_id,
            "what_agent_knew": decision_event.get("memory_snapshot", {}),
            "what_it_queried": reads_near,
            "what_it_decided": {
                "decision": decision_event.get("decision"),
                "reasoning": decision_event.get("reasoning"),
                "context": decision_event.get("context", {}),
            },
            "what_it_wrote": writes_near,
            "causal_chain": {
                "before": reads_near,
                "decision": decision_event,
                "after": writes_near,
            },
            "decision_timestamp": d_ts,
        }

    def reconstruct_state_at(self, agent_id: str, timestamp: float) -> dict:
        """Reconstruct the complete memory state of an agent at a point in time."""
        all_events = self.replay(agent_id, to_ts=timestamp)
        snapshots = [e for e in all_events if e.get("event_type") == "decision" and "memory_snapshot" in e]
        if snapshots:
            return snapshots[-1].get("memory_snapshot", {})

        # Fall back to querying current state
        memory = self.backend.query_prefix(f"agents:{agent_id}:", limit=500)
        state = {}
        for item in memory:
            key = item.get("key", "")
            data = item.get("data", {})
            ts = data.get("timestamp", 0)
            if isinstance(ts, (int, float)):
                ts_sec = ts / 1000000 if ts > 1e12 else ts
            else:
                ts_sec = 0
            if ts_sec <= timestamp:
                state[key] = data.get("value", data)
        return state

    def export_compliance_report(self, agent_id: str, from_ts: float, to_ts: float) -> dict:
        """Export a complete audit trail for compliance."""
        events = self.replay(agent_id, from_ts=from_ts, to_ts=to_ts)

        decisions = [e for e in events if e.get("event_type") == "decision"]
        handoffs_results = self.backend.query_prefix(f"audit:handoffs:", limit=200)
        handoffs = []
        for r in handoffs_results:
            data = r.get("data", {})
            val = data.get("value", data)
            if isinstance(val, dict):
                ts = val.get("timestamp", 0)
                if from_ts <= ts <= to_ts:
                    if val.get("from_agent") == agent_id or val.get("to_agent") == agent_id:
                        handoffs.append(val)

        return {
            "agent_id": agent_id,
            "report_period": {"from": from_ts, "to": to_ts},
            "total_events": len(events),
            "decisions": len(decisions),
            "handoffs": len(handoffs),
            "events": events,
            "handoff_details": handoffs,
            "generated_at": time.time(),
        }

    def get_incident_report(self, agent_id: str, crash_timestamp: float) -> dict:
        """Generate a detailed incident report around a crash."""
        before_events = self.replay(agent_id, from_ts=crash_timestamp - 60, to_ts=crash_timestamp)
        after_events = self.replay(agent_id, from_ts=crash_timestamp, to_ts=crash_timestamp + 60)

        # Get recovery events
        recoveries = self.backend.query_prefix(f"runtime:events:recovery:{agent_id}:", limit=20)
        recovery_event = None
        for r in recoveries:
            data = r.get("data", {})
            val = data.get("value", data)
            if isinstance(val, dict):
                ts = val.get("timestamp", 0)
                if ts >= crash_timestamp and ts <= crash_timestamp + 60:
                    recovery_event = val
                    break

        return {
            "agent_id": agent_id,
            "crash_timestamp": crash_timestamp,
            "before_crash": {
                "events": before_events,
                "event_count": len(before_events),
            },
            "crash_event": {
                "timestamp": crash_timestamp,
                "agent_id": agent_id,
            },
            "recovery": recovery_event or {"status": "no_recovery_found"},
            "after_recovery": {
                "events": after_events,
                "event_count": len(after_events),
            },
        }

    def get_global_timeline(self, limit: int = 50) -> list:
        """Get a global timeline of all audit events across all agents."""
        results = self.backend.query_prefix("audit:", limit=limit * 2)
        events = []
        for r in results:
            data = r.get("data", {})
            val = data.get("value", data)
            if isinstance(val, dict):
                key = r.get("key", "")
                val["_key"] = key
                # Extract event_type from key: audit:{agent}:{ts}:{type}
                parts = key.split(":")
                if len(parts) >= 4 and "event_type" not in val:
                    val["event_type"] = parts[-1]
                events.append(val)
        events.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        return events[:limit]

    def _capture_snapshot(self, agent_id: str) -> dict:
        """Capture current memory state for an agent."""
        try:
            memory = self.backend.query_prefix(f"agents:{agent_id}:", limit=200)
            snapshot = {}
            for item in memory:
                key = item.get("key", "")
                if ":snapshots:" not in key:
                    data = item.get("data", {})
                    snapshot[key] = data.get("value", data)
            return snapshot
        except Exception:
            return {}
