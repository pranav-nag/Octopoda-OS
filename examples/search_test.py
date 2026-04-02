"""
Semantic Search Test — proves the AI pipeline works end-to-end.
Writes memories → searches by meaning → verifies results make sense.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python-sdk"))

from synrix.cloud import Octopoda

API_KEY = os.environ.get("OCTOPODA_API_KEY", "")
BASE_URL = os.environ.get("OCTOPODA_URL", "https://api.octopodas.com")


def main():
    print("=" * 60)
    print("  OCTOPODA — Semantic Search Test")
    print("=" * 60)

    client = Octopoda(api_key=API_KEY, base_url=BASE_URL, timeout=120)
    agent = client.agent("search-test-bot", metadata={"type": "test"})

    # --- Write diverse memories ---
    print("\n[1] Writing test memories...")
    memories = [
        ("pref:diet", {"note": "User is vegetarian and avoids dairy products"}),
        ("pref:location", {"note": "User lives in San Francisco, works remotely"}),
        ("pref:tech", {"note": "Prefers Python and FastAPI for backend development"}),
        ("meeting:jan", {"note": "Discussed Q1 roadmap and hiring plan with CTO"}),
        ("meeting:feb", {"note": "Reviewed sales numbers, revenue up 30% YoY"}),
        ("ticket:auth", {"note": "Customer reported SSO login failing on mobile Safari"}),
        ("ticket:perf", {"note": "Database queries taking 5 seconds on large datasets"}),
        ("config:deploy", {"note": "Production runs on AWS us-east-1 with 3 replicas"}),
    ]

    for key, value in memories:
        result = agent.write(key, value, tags=["search-test"])
        print(f"  Wrote {key} ({result.get('latency_us', 0):.0f}us)")

    # --- Semantic searches ---
    print("\n[2] Running semantic searches...\n")

    queries = [
        ("What does the user eat?", "pref:diet"),
        ("Where does the user live?", "pref:location"),
        ("What programming languages?", "pref:tech"),
        ("revenue and sales performance", "meeting:feb"),
        ("authentication problems", "ticket:auth"),
        ("slow database issues", "ticket:perf"),
        ("cloud infrastructure setup", "config:deploy"),
        ("hiring and team growth", "meeting:jan"),
    ]

    passed = 0
    total = len(queries)

    for query, expected_key in queries:
        results = agent.search(query, limit=3)

        if results:
            top = results[0]
            top_key = top.get("key", "").replace(f"agents:search-test-bot:", "")
            score = top.get("score", 0)
            match = "PASS" if expected_key in top_key else "MISS"
            if expected_key in top_key:
                passed += 1
            print(f"  [{match}] \"{query}\"")
            print(f"    -> Top: {top_key} (score: {score:.4f})")
            if len(results) > 1:
                r2 = results[1]
                print(f"    -> #2:  {r2.get('key', '').replace('agents:search-test-bot:', '')} (score: {r2.get('score', 0):.4f})")
        else:
            print(f"  [MISS] \"{query}\" -> No results (embeddings may not be loaded)")

    print(f"\n  Results: {passed}/{total} correct top matches")
    accuracy = passed / total * 100 if total > 0 else 0
    print(f"  Accuracy: {accuracy:.0f}%")

    if accuracy >= 75:
        print(f"\n  SEMANTIC SEARCH WORKING -- {accuracy:.0f}% accuracy")
    elif accuracy >= 50:
        print(f"\n  PARTIAL -- {accuracy:.0f}% (embeddings may need Ollama fact extraction)")
    else:
        print(f"\n  LOW ACCURACY -- embeddings may not be generating on writes")

    print("\n" + "=" * 60)
    client.close()


if __name__ == "__main__":
    main()
