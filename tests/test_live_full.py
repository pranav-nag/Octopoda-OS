"""
Full Live E2E Test — Fresh Server
===================================
Creates 2 accounts from scratch, registers agents, tests every endpoint,
verifies tenant isolation. Run against the live VPS.

Run: python -m pytest tests/test_live_full.py -v -s --tb=short
"""

import time
import requests
import pytest

API = "https://api.octopodas.com"

# Test accounts — created fresh each run
USER_A = {"email": "testa@octopoda-test.com", "password": "TestPass123!", "first_name": "Alice", "last_name": "Tester"}
USER_B = {"email": "testb@octopoda-test.com", "password": "TestPass456!", "first_name": "Bob", "last_name": "Checker"}

# Will be set during signup
KEY_A = None
KEY_B = None
TENANT_A = None
TENANT_B = None


def _h(key):
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _get(path, key, timeout=30):
    return requests.get(f"{API}{path}", headers=_h(key), timeout=timeout)


def _post(path, data=None, key=None, timeout=30):
    headers = _h(key) if key else {"Content-Type": "application/json"}
    return requests.post(f"{API}{path}", json=data, headers=headers, timeout=timeout)


def _put(path, data=None, key=None):
    return requests.put(f"{API}{path}", json=data, headers=_h(key), timeout=30)


def _delete(path, key):
    return requests.delete(f"{API}{path}", headers=_h(key), timeout=30)


# ===================================================================
# 0. HEALTH CHECK
# ===================================================================

class Test00Health:
    def test_server_is_alive(self):
        resp = requests.get(f"{API}/health", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "2.0.0"
        print(f"  Server up - uptime {data['uptime_seconds']:.0f}s")


# ===================================================================
# 1. AUTH — Create two accounts
# ===================================================================

class Test01Auth:

    def test_signup_user_a(self):
        global KEY_A, TENANT_A
        resp = _post("/v1/auth/signup", USER_A)
        assert resp.status_code == 200, f"Signup A failed: {resp.text}"
        data = resp.json()
        assert data["success"] is True
        assert data["api_key"].startswith("sk-octopoda-")
        KEY_A = data["api_key"]
        TENANT_A = data["tenant_id"]
        print(f"  User A signed up: tenant={TENANT_A}")

    def test_signup_user_b(self):
        global KEY_B, TENANT_B
        resp = _post("/v1/auth/signup", USER_B)
        assert resp.status_code == 200, f"Signup B failed: {resp.text}"
        data = resp.json()
        assert data["success"] is True
        KEY_B = data["api_key"]
        TENANT_B = data["tenant_id"]
        print(f"  User B signed up: tenant={TENANT_B}")
        assert TENANT_A != TENANT_B, "Tenants must be different!"

    def test_unverified_blocked(self):
        """Unverified accounts should be blocked from API calls."""
        resp = _get("/v1/agents", KEY_A)
        assert resp.status_code == 403, f"Expected 403 for unverified, got {resp.status_code}"
        print(f"  Unverified correctly blocked (403)")

    def test_verify_accounts(self):
        """Force-verify both accounts via direct DB call on VPS."""
        import paramiko
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            os.environ.get("OCTOPODA_VPS_HOST", "localhost"),
            username="root",
            password=os.environ.get("OCTOPODA_VPS_PASSWORD", ""),
            timeout=10
        )
        cmd = (
            f"python3 -c \""
            f"import sqlite3; "
            f"db = sqlite3.connect('/root/.synrix/data/tenant_registry.db'); "
            f"db.execute('UPDATE tenants SET verified=1 WHERE email IN (\\'{USER_A['email']}\\', \\'{USER_B['email']}\\')'); "
            f"db.commit(); "
            f"print('Verified', db.execute('SELECT COUNT(*) FROM tenants WHERE verified=1').fetchone()[0], 'accounts'); "
            f"db.close()\""
        )
        stdin, stdout, stderr = ssh.exec_command(cmd)
        print(f"  {stdout.read().decode().strip()}")
        ssh.close()

    def test_verified_can_access(self):
        """After verification, API calls should work."""
        resp = _get("/v1/agents", KEY_A)
        assert resp.status_code == 200, f"Expected 200 after verify, got {resp.status_code}: {resp.text}"
        assert resp.json()["total"] == 0
        print(f"  Verified User A can access API (0 agents)")

    def test_login_works(self):
        """Login returns a working API key."""
        resp = _post("/v1/auth/login", {"email": USER_A["email"], "password": USER_A["password"]})
        assert resp.status_code == 200
        data = resp.json()
        assert data["api_key"].startswith("sk-octopoda-")
        assert data["tenant_id"] == TENANT_A
        print(f"  Login works, got fresh key")

    def test_auth_me(self):
        resp = _get("/v1/auth/me", KEY_A)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == USER_A["email"]
        print(f"  /auth/me returns correct email")

    def test_wrong_password_fails(self):
        resp = _post("/v1/auth/login", {"email": USER_A["email"], "password": "WrongPassword!"})
        assert resp.status_code == 401
        print(f"  Wrong password correctly rejected (401)")

    def test_invalid_key_fails(self):
        resp = _get("/v1/agents", "sk-octopoda-totally-fake-key")
        assert resp.status_code == 401
        print(f"  Invalid API key correctly rejected (401)")


# ===================================================================
# 2. AGENT MANAGEMENT — User A registers 5 agents
# ===================================================================

class Test02Agents:

    def test_register_agents_user_a(self):
        agents = [
            ("research-bot", "research"),
            ("chat-bot", "chat"),
            ("analysis-bot", "analysis"),
            ("monitor-bot", "monitoring"),
            ("auto-bot", "automation"),
        ]
        for agent_id, agent_type in agents:
            resp = _post(f"/v1/agents", {"agent_id": agent_id, "agent_type": agent_type}, key=KEY_A)
            assert resp.status_code == 200, f"Register {agent_id} failed: {resp.text}"
        print(f"  User A: registered 5 agents")

    def test_list_agents_user_a(self):
        resp = _get("/v1/agents?offset=0&limit=100", KEY_A)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        print(f"  User A: lists 5 agents")

    def test_get_agent_detail(self):
        resp = _get("/v1/agents/research-bot", KEY_A)
        assert resp.status_code == 200
        assert resp.json()["agent_id"] == "research-bot"
        print(f"  Agent detail works")

    def test_register_agents_user_b(self):
        """User B registers 2 different agents."""
        for agent_id in ["bob-agent-1", "bob-agent-2"]:
            resp = _post(f"/v1/agents", {"agent_id": agent_id, "agent_type": "generic"}, key=KEY_B)
            assert resp.status_code == 200
        resp = _get("/v1/agents", KEY_B)
        assert resp.json()["total"] == 2
        print(f"  User B: registered 2 agents")


# ===================================================================
# 3. MEMORY OPERATIONS
# ===================================================================

class Test03Memory:

    def test_remember_and_recall(self):
        resp = _post("/v1/agents/research-bot/remember", {
            "key": "project:name", "value": "Octopoda Memory Engine"
        }, key=KEY_A)
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        resp = _get("/v1/agents/research-bot/recall/project:name", KEY_A)
        assert resp.status_code == 200
        assert resp.json()["found"] is True
        assert "Octopoda" in str(resp.json()["value"])
        print(f"  Remember + recall works")

    def test_multiple_writes(self):
        writes = [
            ("config:model", "gpt-4"),
            ("config:temp", "0.7"),
            ("user:name", "Alice"),
            ("user:role", "researcher"),
            ("task:current", "Analyzing patterns"),
        ]
        for key, value in writes:
            resp = _post("/v1/agents/research-bot/remember", {"key": key, "value": value}, key=KEY_A)
            assert resp.json()["success"] is True
        print(f"  Wrote 5 memories to research-bot")

    def test_search(self):
        resp = _get("/v1/agents/research-bot/search?prefix=config:&limit=50", KEY_A)
        assert resp.status_code == 200
        assert resp.json()["count"] == 2
        print(f"  Search: found {resp.json()['count']} config keys")

    def test_list_memory(self):
        resp = _get("/v1/agents/research-bot/memory?offset=0&limit=50", KEY_A)
        assert resp.status_code == 200
        assert resp.json()["count"] >= 6
        print(f"  Memory list: {resp.json()['count']} items")

    def test_remember_with_tags(self):
        resp = _post("/v1/agents/chat-bot/remember", {
            "key": "insight:1",
            "value": "Users prefer concise responses",
            "tags": ["ux", "important"]
        }, key=KEY_A)
        assert resp.json()["success"] is True
        print(f"  Tags working")

    def test_batch_remember(self):
        items = [{"key": f"data:{i}", "value": f"Batch item {i}"} for i in range(5)]
        resp = _post("/v1/agents/analysis-bot/remember/batch", {"items": items}, key=KEY_A, timeout=60)
        assert resp.status_code == 200
        assert resp.json()["count"] == 5
        print(f"  Batch: wrote 5 items")

    def test_user_b_writes_memory(self):
        resp = _post("/v1/agents/bob-agent-1/remember", {
            "key": "secret", "value": "Bob's private data"
        }, key=KEY_B)
        assert resp.json()["success"] is True
        print(f"  User B wrote memory")


# ===================================================================
# 4. SHARED MEMORY
# ===================================================================

class Test04SharedMemory:

    def test_write_shared(self):
        resp = _post("/v1/shared/team-space", {
            "key": "goal", "value": "Ship v2.0", "author_agent_id": "research-bot"
        }, key=KEY_A)
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        print(f"  Shared write OK")

    def test_multiple_agents_share(self):
        for agent in ["research-bot", "chat-bot", "analysis-bot"]:
            _post("/v1/shared/collab", {
                "key": f"update:{agent}", "value": f"Status from {agent}",
                "author_agent_id": agent
            }, key=KEY_A)
        print(f"  3 agents wrote to shared space")

    def test_read_shared(self):
        resp = _get("/v1/shared/team-space/goal", KEY_A)
        assert resp.status_code == 200
        assert resp.json()["found"] is True
        print(f"  Shared read OK")

    def test_list_shared_space(self):
        resp = _get("/v1/shared/collab", KEY_A)
        assert resp.status_code == 200
        assert resp.json()["count"] >= 3
        print(f"  Shared space: {resp.json()['count']} items")

    def test_list_all_spaces(self):
        resp = _get("/v1/shared", KEY_A)
        assert resp.status_code == 200
        assert len(resp.json()["spaces"]) >= 2
        print(f"  {len(resp.json()['spaces'])} shared spaces")

    def test_shared_detail(self):
        resp = _get("/v1/shared/collab/detail", KEY_A)
        assert resp.status_code == 200
        assert "items" in resp.json()
        print(f"  Shared detail OK")

    def test_user_b_shared(self):
        _post("/v1/shared/bob-space", {
            "key": "private", "value": "Bob only", "author_agent_id": "bob-agent-1"
        }, key=KEY_B)
        print(f"  User B shared space created")


# ===================================================================
# 5. AUDIT TRAIL & DECISIONS
# ===================================================================

class Test05Audit:

    def test_log_decision(self):
        resp = _post("/v1/agents/research-bot/decision", {
            "decision": "Use RAG pipeline",
            "reasoning": "Domain queries need retrieval augmentation"
        }, key=KEY_A)
        assert resp.status_code == 200
        assert resp.json()["logged"] is True
        print(f"  Decision logged")

    def test_multiple_decisions(self):
        _post("/v1/agents/chat-bot/decision", {
            "decision": "Enable streaming", "reasoning": "Lower latency"
        }, key=KEY_A)
        _post("/v1/agents/analysis-bot/decision", {
            "decision": "Increase sample", "reasoning": "Need n>1000"
        }, key=KEY_A)
        print(f"  3 decisions total")

    def test_agent_audit_trail(self):
        resp = _get("/v1/agents/research-bot/audit?limit=50", KEY_A)
        assert resp.status_code == 200
        assert "events" in resp.json()
        print(f"  Audit trail: {resp.json().get('count', len(resp.json()['events']))} events")

    def test_global_timeline(self):
        resp = _get("/v1/audit/timeline?limit=50", KEY_A)
        assert resp.status_code == 200
        assert "events" in resp.json()
        print(f"  Global timeline: {len(resp.json()['events'])} events")

    def test_audit_replay(self):
        now = time.time()
        resp = _get(f"/v1/agents/research-bot/audit/replay?from={now-3600}&to={now}", KEY_A)
        assert resp.status_code == 200
        print(f"  Audit replay OK")


# ===================================================================
# 6. METRICS & ANALYTICS
# ===================================================================

class Test06Metrics:

    def test_agent_metrics(self):
        resp = _get("/v1/agents/research-bot/metrics", KEY_A)
        assert resp.status_code == 200
        assert resp.json()["agent_id"] == "research-bot"
        print(f"  Agent metrics OK")

    def test_agent_timeseries(self):
        resp = _get("/v1/agents/research-bot/metrics/timeseries?minutes=60&type=write", KEY_A)
        assert resp.status_code == 200
        print(f"  Agent timeseries OK")

    def test_agent_analytics(self):
        resp = _get("/v1/agents/research-bot/analytics", KEY_A)
        assert resp.status_code == 200
        print(f"  Agent analytics OK")

    def test_agent_performance(self):
        resp = _get("/v1/agents/research-bot/performance", KEY_A)
        assert resp.status_code == 200
        print(f"  Agent performance OK")

    def test_system_metrics(self):
        resp = _get("/v1/metrics/system", KEY_A)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("active_agents", 0) >= 5
        print(f"  System metrics: {data.get('active_agents', '?')} active agents")

    def test_anomalies(self):
        resp = _get("/v1/anomalies", KEY_A)
        assert resp.status_code == 200
        print(f"  Anomalies endpoint OK")


# ===================================================================
# 7. SNAPSHOTS & RECOVERY
# ===================================================================

class Test07Recovery:

    def test_snapshot(self):
        resp = _post("/v1/agents/research-bot/snapshot", {"label": "test_v1"}, key=KEY_A)
        assert resp.status_code == 200
        assert resp.json()["keys_captured"] >= 1
        print(f"  Snapshot: {resp.json()['keys_captured']} keys captured")

    def test_restore(self):
        resp = _post("/v1/agents/research-bot/restore", {"label": "test_v1"}, key=KEY_A)
        assert resp.status_code == 200
        assert resp.json()["keys_restored"] >= 1
        print(f"  Restore: {resp.json()['keys_restored']} keys restored")

    def test_recovery_history(self):
        resp = _get("/v1/recovery/history", KEY_A)
        assert resp.status_code == 200
        assert "history" in resp.json()
        print(f"  Recovery history OK")

    def test_cleanup(self):
        resp = _post("/v1/agents/research-bot/cleanup", key=KEY_A)
        assert resp.status_code == 200
        print(f"  Cleanup OK")


# ===================================================================
# 8. RAW OPERATIONS
# ===================================================================

class Test08Raw:

    def test_raw_write_read(self):
        _post("/v1/raw/write", {"key": "test:raw", "value": {"x": 42}}, key=KEY_A)
        resp = _get("/v1/raw/read/test:raw", KEY_A)
        assert resp.json()["found"] is True
        print(f"  Raw write/read OK")

    def test_raw_query(self):
        _post("/v1/raw/write", {"key": "ns:a", "value": 1}, key=KEY_A)
        _post("/v1/raw/write", {"key": "ns:b", "value": 2}, key=KEY_A)
        resp = _get("/v1/raw/query?prefix=ns:", KEY_A)
        assert resp.json()["count"] >= 2
        print(f"  Raw query: {resp.json()['count']} results")


# ===================================================================
# 9. SETTINGS
# ===================================================================

class Test09Settings:

    def test_get_settings(self):
        resp = _get("/v1/settings", KEY_A)
        assert resp.status_code == 200
        print(f"  GET settings OK")

    def test_put_settings(self):
        resp = _put("/v1/settings", {"llm_provider": "none"}, key=KEY_A)
        assert resp.status_code == 200
        print(f"  PUT settings OK")


# ===================================================================
# 10. SSE STREAM
# ===================================================================

class Test10SSE:

    def test_sse_connects(self):
        """SSE endpoint should return 200 and start streaming."""
        resp = requests.get(
            f"{API}/v1/stream/events",
            headers=_h(KEY_A),
            stream=True, timeout=5
        )
        assert resp.status_code == 200
        resp.close()
        print(f"  SSE stream connects OK")


# ===================================================================
# 11. TENANT ISOLATION
# ===================================================================

class Test11TenantIsolation:

    def test_agents_isolated(self):
        """User B cannot see User A's agents."""
        resp = _get("/v1/agents", KEY_B)
        agent_ids = [a["agent_id"] for a in resp.json()["agents"]]
        a_agents = {"research-bot", "chat-bot", "analysis-bot", "monitor-bot", "auto-bot"}
        leaked = a_agents & set(agent_ids)
        assert len(leaked) == 0, f"LEAK: User B sees User A's agents: {leaked}"
        assert resp.json()["total"] == 2  # Only bob's 2
        print(f"  User B sees only their 2 agents")

    def test_user_a_cannot_see_b(self):
        """User A cannot see User B's agents."""
        resp = _get("/v1/agents", KEY_A)
        agent_ids = [a["agent_id"] for a in resp.json()["agents"]]
        assert "bob-agent-1" not in agent_ids
        assert "bob-agent-2" not in agent_ids
        print(f"  User A cannot see User B's agents")

    def test_memory_isolated(self):
        """User A cannot read User B's memories."""
        # User B wrote to bob-agent-1/secret
        # User A tries with same agent name
        _post("/v1/agents", {"agent_id": "bob-agent-1"}, key=KEY_A)
        resp = _get("/v1/agents/bob-agent-1/recall/secret", KEY_A)
        assert resp.json()["found"] is False, "LEAK: User A can read User B's memory!"
        print(f"  Memory isolated between tenants")

    def test_shared_memory_isolated(self):
        """User A cannot read User B's shared spaces."""
        resp = _get("/v1/shared/bob-space/private", KEY_A)
        assert resp.json()["found"] is False, "LEAK: User A reads User B's shared memory!"
        print(f"  Shared memory isolated")

    def test_raw_isolated(self):
        """User B cannot read User A's raw data."""
        resp = _get("/v1/raw/read/test:raw", KEY_B)
        assert resp.json()["found"] is False, "LEAK: User B reads User A's raw data!"
        print(f"  Raw data isolated")

    def test_audit_isolated(self):
        """User B has no audit events from User A."""
        resp = _get("/v1/agents/research-bot/audit", KEY_B)
        # Either 200 with empty events (agent doesn't exist in B) or works
        if resp.status_code == 200:
            assert resp.json().get("count", 0) == 0
        print(f"  Audit isolated")

    def test_metrics_isolated(self):
        """System metrics are per-tenant."""
        resp_a = _get("/v1/metrics/system", KEY_A)
        resp_b = _get("/v1/metrics/system", KEY_B)
        assert resp_a.status_code == 200
        assert resp_b.status_code == 200
        # A should have more agents than B
        a_agents = resp_a.json().get("active_agents", 0)
        b_agents = resp_b.json().get("active_agents", 0)
        assert a_agents > b_agents, f"Metrics not isolated: A={a_agents}, B={b_agents}"
        print(f"  Metrics isolated: A={a_agents} agents, B={b_agents} agents")


# ===================================================================
# 12. DASHBOARD ENDPOINT COVERAGE
# ===================================================================

class Test12DashboardEndpoints:
    """Verify every endpoint the Lovable dashboard calls."""

    def test_all_dashboard_endpoints_respond(self):
        endpoints = [
            ("GET", "/v1/agents?offset=0&limit=100"),
            ("GET", "/v1/agents/research-bot"),
            ("GET", "/v1/agents/research-bot/memory?offset=0&limit=50"),
            ("GET", "/v1/agents/research-bot/search?limit=50"),
            ("GET", "/v1/agents/research-bot/audit?limit=50"),
            ("GET", "/v1/agents/research-bot/analytics"),
            ("GET", "/v1/agents/research-bot/metrics/timeseries?minutes=60&type=write"),
            ("GET", "/v1/metrics/system"),
            ("GET", "/v1/anomalies"),
            ("GET", "/v1/recovery/history"),
            ("GET", "/v1/audit/timeline?limit=50"),
            ("GET", "/v1/shared"),
            ("GET", "/v1/shared/team-space/detail"),
            ("GET", "/v1/settings"),
            ("GET", "/v1/auth/me"),
        ]
        passed = 0
        for method, path in endpoints:
            resp = _get(path, KEY_A)
            assert resp.status_code == 200, f"{method} {path} returned {resp.status_code}"
            passed += 1
        print(f"  All {passed} dashboard endpoints responding (200)")


# ===================================================================
# 13. CLEANUP — Delete test accounts
# ===================================================================

class Test13Cleanup:

    def test_delete_accounts(self):
        """Clean up test accounts."""
        resp_a = _delete("/v1/auth/account", KEY_A)
        resp_b = _delete("/v1/auth/account", KEY_B)
        assert resp_a.status_code == 200
        assert resp_b.status_code == 200
        print(f"  Both test accounts deleted")

    def test_deleted_key_fails(self):
        """Deleted account's key should no longer work."""
        resp = _get("/v1/agents", KEY_A)
        assert resp.status_code == 401
        print(f"  Deleted key correctly rejected")
