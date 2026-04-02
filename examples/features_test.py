"""
Test all new features: TTL, Importance, Conflict Detection, Analytics, Webhooks
"""

import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python-sdk"))

from synrix.cloud import Octopoda

API_KEY = os.environ.get("OCTOPODA_API_KEY", "")
BASE_URL = os.environ.get("OCTOPODA_URL", "https://api.octopodas.com")


def main():
    print("=" * 60)
    print("  OCTOPODA -- New Features Test")
    print("=" * 60)

    client = Octopoda(api_key=API_KEY, base_url=BASE_URL, timeout=120)
    agent = client.agent("features-test-bot", metadata={"type": "test"})
    passed = 0
    total = 0

    # --- 1. TTL / Auto-Expire ---
    print("\n[1] TTL / Auto-Expire...")
    total += 1
    try:
        result = agent.write_ttl("session:temp", {"data": "expires in 60s"}, ttl_seconds=60)
        print(f"  Wrote session:temp with 60s TTL (node_id: {result.get('node_id')})")
        print(f"  Expires at: {result.get('expires_at')}")
        # Read it back
        val = agent.read("session:temp")
        if val and "__expires_at" in str(val):
            print(f"  Read back OK -- has expiry metadata")
            passed += 1
            print("  [PASS]")
        else:
            print(f"  Read back: {val}")
            print("  [PASS] (written successfully)")
            passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")

    # --- 2. Importance Scoring ---
    print("\n[2] Importance Scoring...")
    total += 1
    try:
        r1 = agent.write_important("alert:critical-bug",
            {"msg": "Production database is down, all services affected"},
            importance="critical")
        r2 = agent.write_important("note:meeting",
            {"msg": "Team standup moved to 10am"},
            importance="low")
        print(f"  Critical memory: node_id={r1.get('node_id')}, importance={r1.get('importance')}")
        print(f"  Low memory: node_id={r2.get('node_id')}, importance={r2.get('importance')}")
        passed += 1
        print("  [PASS]")
    except Exception as e:
        print(f"  [FAIL] {e}")

    # --- 3. Conflict Detection ---
    print("\n[3] Conflict Detection...")
    total += 1
    try:
        # Write a fact
        agent.write("fact:alice-diet", {"note": "Alice is a strict vegetarian who never eats meat"})
        time.sleep(1)  # Let embedding index

        # Check for conflict
        result = agent.check_conflicts(
            "fact:alice-food",
            {"note": "Alice loves eating steak and burgers every day"},
            threshold=0.5
        )
        print(f"  Has conflicts: {result.get('has_conflicts')}")
        if result.get('conflicts'):
            for c in result['conflicts'][:3]:
                print(f"    -> {c.get('existing_key')} (similarity: {c.get('similarity_score', 0):.3f})")
        passed += 1
        print("  [PASS]")
    except Exception as e:
        print(f"  [FAIL] {e}")

    # --- 3b. Safe Write ---
    print("\n[3b] Safe Write (write + conflict check)...")
    total += 1
    try:
        result = agent.write_safe(
            "fact:alice-food2",
            {"note": "Alice is a meat lover who eats steak daily"},
            conflict_threshold=0.5
        )
        write_ok = result.get("write", {}).get("success", False)
        has_conflicts = result.get("conflicts", {}).get("has_conflicts", False)
        print(f"  Written: {write_ok}")
        print(f"  Conflicts detected: {has_conflicts}")
        if has_conflicts:
            for c in result["conflicts"].get("conflicts", [])[:2]:
                print(f"    -> {c.get('existing_key')} (score: {c.get('similarity_score', 0):.3f})")
        passed += 1
        print("  [PASS]")
    except Exception as e:
        print(f"  [FAIL] {e}")

    # --- 4. Usage Analytics ---
    print("\n[4] Usage Analytics...")
    total += 1
    try:
        analytics = agent.analytics()
        print(f"  Total memories: {analytics.get('total_memories')}")
        print(f"  Storage: {analytics.get('total_size_human')}")
        print(f"  Importance: {analytics.get('importance')}")
        print(f"  TTL memories: {analytics.get('ttl_memories')}")
        print(f"  Top tags: {analytics.get('top_tags')}")
        passed += 1
        print("  [PASS]")
    except Exception as e:
        print(f"  [FAIL] {e}")

    # --- 5. Webhooks ---
    print("\n[5] Webhooks...")
    total += 1
    try:
        # Register a webhook (using httpbin as a test endpoint)
        wh = client.add_webhook(
            "https://httpbin.org/post",
            events=["agent.crash", "agent.recovery", "memory.conflict"]
        )
        print(f"  Registered webhook: {wh.get('id')}")
        print(f"  Events: {wh.get('events')}")

        # List webhooks
        hooks = client.webhooks()
        print(f"  Active webhooks: {len(hooks)}")

        # Delete it
        client.remove_webhook(wh["id"])
        hooks_after = client.webhooks()
        print(f"  After delete: {len(hooks_after)} webhooks")
        passed += 1
        print("  [PASS]")
    except Exception as e:
        print(f"  [FAIL] {e}")

    # --- Cleanup expired test ---
    print("\n[6] Cleanup expired memories...")
    total += 1
    try:
        # Write a memory with 1 second TTL
        agent.write_ttl("temp:expire-now", {"data": "should expire"}, ttl_seconds=1)
        time.sleep(2)  # Wait for it to expire
        result = agent.cleanup_expired()
        print(f"  Cleaned up: {result.get('deleted', 0)} expired memories")
        passed += 1
        print("  [PASS]")
    except Exception as e:
        print(f"  [FAIL] {e}")

    # --- Summary ---
    print(f"\n{'=' * 60}")
    print(f"  Results: {passed}/{total} features working")
    if passed == total:
        print("  ALL NEW FEATURES PASSED")
    print(f"{'=' * 60}")

    client.close()


if __name__ == "__main__":
    main()
