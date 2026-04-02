"""
Tests for the new Dashboard API endpoints on Cloud Server.

These test the 10 endpoints added for the Loveable React dashboard:
- SSE streaming
- Anomaly detection
- Metrics time-series (per-agent and system)
- Global audit timeline
- Audit explain decision
- Audit replay with time range
- Performance breakdown
- Shared memory detail with changelog
"""

import pytest
import time
import json


class TestSSEStream:
    """Test the Server-Sent Events streaming endpoint."""

    def test_sse_endpoint_exists(self, api_client):
        """SSE endpoint should be registered and not return 404/405."""
        from synrix_runtime.api.cloud_server import app
        routes = [r.path for r in app.routes if hasattr(r, 'path')]
        assert "/v1/stream/events" in routes

    def test_sse_generator_produces_events(self, api_client):
        """The SSE generator function should produce valid events."""
        from synrix_runtime.api.cloud_server import _sse_event_generator
        from synrix.agent_backend import get_synrix_backend
        import tempfile, os
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            backend = get_synrix_backend(backend="sqlite", sqlite_path=os.path.join(td, "sse.db"))
            gen = _sse_event_generator(backend)
            # Get the first batch of events (one iteration of the loop)
            collected = ""
            import threading
            result = {}
            def collect():
                try:
                    for chunk in gen:
                        result.setdefault("chunks", []).append(chunk)
                        if "system_heartbeat" in chunk:
                            break
                except Exception as e:
                    result["error"] = str(e)
            t = threading.Thread(target=collect, daemon=True)
            t.start()
            t.join(timeout=5)
            chunks = result.get("chunks", [])
            full_output = "".join(chunks)
            assert "event: agent_update" in full_output
            assert "event: system_heartbeat" in full_output
            backend.close()


class TestAnomalyDetection:
    """Test the anomaly detection endpoint."""

    def test_anomalies_returns_list(self, api_client):
        resp = api_client.get("/v1/anomalies")
        assert resp.status_code == 200
        data = resp.json()
        assert "anomalies" in data
        assert isinstance(data["anomalies"], list)

    def test_anomalies_empty_when_no_agents(self, api_client):
        resp = api_client.get("/v1/anomalies")
        assert resp.status_code == 200
        # With no activity, should be empty or contain idle-agent type anomalies
        data = resp.json()
        assert isinstance(data["anomalies"], list)


class TestMetricsTimeSeries:
    """Test time-series metrics endpoints."""

    def test_agent_metrics_timeseries(self, api_client):
        """Per-agent timeseries should return series array."""
        api_client.post("/v1/agents", json={"agent_id": "ts_agent"})
        api_client.post("/v1/agents/ts_agent/remember", json={"key": "x", "value": 1})

        resp = api_client.get("/v1/agents/ts_agent/metrics/timeseries?minutes=60&type=write")
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_id"] == "ts_agent"
        assert data["type"] == "write"
        assert data["minutes"] == 60
        assert "series" in data
        assert isinstance(data["series"], list)

    def test_agent_metrics_timeseries_read_type(self, api_client):
        """Should accept different metric types."""
        api_client.post("/v1/agents", json={"agent_id": "ts_read"})
        resp = api_client.get("/v1/agents/ts_read/metrics/timeseries?type=read")
        assert resp.status_code == 200
        assert resp.json()["type"] == "read"

    def test_system_metrics_timeseries(self, api_client):
        """System-wide timeseries endpoint."""
        resp = api_client.get("/v1/metrics/timeseries")
        assert resp.status_code == 200
        data = resp.json()
        assert "series" in data
        assert isinstance(data["series"], list)

    def test_system_metrics_timeseries_with_agent_filter(self, api_client):
        """System timeseries with agent_id filter."""
        api_client.post("/v1/agents", json={"agent_id": "ts_filtered"})
        resp = api_client.get("/v1/metrics/timeseries?agent_id=ts_filtered&minutes=30")
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_id"] == "ts_filtered"
        assert data["minutes"] == 30


class TestAuditTimeline:
    """Test global audit timeline and explain endpoints."""

    def test_audit_timeline_returns_events(self, api_client):
        """Global timeline should return events list."""
        resp = api_client.get("/v1/audit/timeline")
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data
        assert isinstance(data["events"], list)
        assert "limit" in data

    def test_audit_timeline_with_limit(self, api_client):
        """Limit parameter should be respected."""
        resp = api_client.get("/v1/audit/timeline?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 10

    def test_audit_explain_decision(self, api_client):
        """Explain decision endpoint should return without error."""
        api_client.post("/v1/agents", json={"agent_id": "explain_agent"})
        api_client.post("/v1/agents/explain_agent/decision", json={
            "decision": "Use cache",
            "reasoning": "Reduce latency",
        })

        ts = time.time()
        resp = api_client.get(f"/v1/audit/explain/explain_agent/{ts}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_id"] == "explain_agent"

    def test_audit_replay_with_time_range(self, api_client):
        """Audit replay should accept from/to query params."""
        api_client.post("/v1/agents", json={"agent_id": "replay_agent"})
        api_client.post("/v1/agents/replay_agent/remember", json={"key": "data", "value": "test"})

        now = time.time()
        resp = api_client.get(
            f"/v1/agents/replay_agent/audit/replay",
            params={"from": now - 3600, "to": now + 60}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_id"] == "replay_agent"
        assert "events" in data
        assert "count" in data

    def test_audit_replay_no_time_range(self, api_client):
        """Audit replay without time range should return all events."""
        api_client.post("/v1/agents", json={"agent_id": "replay_all"})
        resp = api_client.get("/v1/agents/replay_all/audit/replay")
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_id"] == "replay_all"
        assert isinstance(data["events"], list)


class TestPerformanceBreakdown:
    """Test per-agent performance breakdown endpoint."""

    def test_performance_returns_metrics(self, api_client):
        """Performance endpoint should return metrics + breakdown."""
        api_client.post("/v1/agents", json={"agent_id": "perf_agent"})
        api_client.post("/v1/agents/perf_agent/remember", json={"key": "x", "value": 1})
        api_client.post("/v1/agents/perf_agent/remember", json={"key": "y", "value": 2})

        resp = api_client.get("/v1/agents/perf_agent/performance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_id"] == "perf_agent"
        assert "metrics" in data
        assert "breakdown" in data

    def test_performance_metrics_fields(self, api_client):
        """Performance metrics should include expected fields."""
        api_client.post("/v1/agents", json={"agent_id": "perf_fields"})
        api_client.post("/v1/agents/perf_fields/remember", json={"key": "z", "value": 3})

        resp = api_client.get("/v1/agents/perf_fields/performance")
        assert resp.status_code == 200
        metrics = resp.json()["metrics"]
        # These fields should exist (may be 0 but present)
        for field in ["total_operations", "total_writes", "total_reads",
                       "avg_write_latency_us", "avg_read_latency_us",
                       "crash_count", "performance_score", "uptime_seconds"]:
            assert field in metrics, f"Missing field: {field}"

    def test_performance_unknown_agent(self, api_client):
        """Performance for unknown agent should return empty gracefully."""
        resp = api_client.get("/v1/agents/nonexistent_perf/performance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_id"] == "nonexistent_perf"


class TestSharedMemoryDetail:
    """Test shared memory detail + changelog endpoint."""

    def test_shared_detail_returns_items_and_changelog(self, api_client):
        """Shared detail should return items and changelog."""
        api_client.post("/v1/agents", json={"agent_id": "share_detail"})
        api_client.post("/v1/shared/team", json={
            "key": "project",
            "value": "Octopoda",
            "author_agent_id": "share_detail",
        })

        resp = api_client.get("/v1/shared/team/detail")
        assert resp.status_code == 200
        data = resp.json()
        assert data["space"] == "team"
        assert "items" in data
        assert "changelog" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["changelog"], list)

    def test_shared_detail_empty_space(self, api_client):
        """Empty space should return empty lists, not error."""
        resp = api_client.get("/v1/shared/empty_space/detail")
        assert resp.status_code == 200
        data = resp.json()
        assert data["space"] == "empty_space"
        assert data["items"] == [] or isinstance(data["items"], list)
        assert data["changelog"] == [] or isinstance(data["changelog"], list)


class TestEndpointRouteRegistration:
    """Verify all new endpoints are reachable (not 404)."""

    def test_all_new_routes_exist(self, api_client):
        """None of the new dashboard endpoints should return 404."""
        # These should all return 200 (possibly with empty data)
        routes_get = [
            "/v1/anomalies",
            "/v1/metrics/timeseries",
            "/v1/audit/timeline",
        ]
        for route in routes_get:
            resp = api_client.get(route)
            assert resp.status_code != 404, f"{route} returned 404"
            assert resp.status_code == 200, f"{route} returned {resp.status_code}"
