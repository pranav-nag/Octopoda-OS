"""
Tests for SynrixSQLiteClient — the persistent backend.
Proves: write/read roundtrip, prefix queries, concurrent writes, persistence.
"""

import os
import threading
import pytest


class TestSQLiteRoundtrip:
    """Basic write and read operations."""

    def test_write_and_read(self, sqlite_client):
        node_id = sqlite_client.add_node("test:key1", '{"value": "hello"}', collection="mem")
        assert node_id is not None

        results = sqlite_client.query_prefix("test:key1", collection="mem", limit=10)
        assert len(results) == 1
        assert results[0]["payload"]["name"] == "test:key1"
        assert results[0]["payload"]["data"] == '{"value": "hello"}'

    def test_overwrite_same_key(self, sqlite_client):
        sqlite_client.add_node("key", "v1", collection="c")
        sqlite_client.add_node("key", "v2", collection="c")

        results = sqlite_client.query_prefix("key", collection="c")
        assert len(results) == 1
        assert results[0]["payload"]["data"] == "v2"

    def test_empty_data(self, sqlite_client):
        node_id = sqlite_client.add_node("empty", "", collection="c")
        assert node_id is not None
        results = sqlite_client.query_prefix("empty", collection="c")
        assert len(results) == 1
        assert results[0]["payload"]["data"] == ""


class TestSQLitePrefixQuery:
    """Prefix-based search."""

    def test_prefix_filters_correctly(self, sqlite_client):
        sqlite_client.add_node("agents:a1:mem:k1", "d1", collection="m")
        sqlite_client.add_node("agents:a1:mem:k2", "d2", collection="m")
        sqlite_client.add_node("agents:a2:mem:k1", "d3", collection="m")
        sqlite_client.add_node("metrics:sys:ops", "d4", collection="m")

        results = sqlite_client.query_prefix("agents:a1:", collection="m")
        assert len(results) == 2
        names = {r["payload"]["name"] for r in results}
        assert names == {"agents:a1:mem:k1", "agents:a1:mem:k2"}

    def test_limit_respected(self, sqlite_client):
        for i in range(20):
            sqlite_client.add_node(f"batch:{i:03d}", f"data_{i}", collection="c")

        results = sqlite_client.query_prefix("batch:", collection="c", limit=5)
        assert len(results) == 5

    def test_empty_prefix_returns_all(self, sqlite_client):
        sqlite_client.add_node("a", "1", collection="c")
        sqlite_client.add_node("b", "2", collection="c")
        sqlite_client.add_node("c", "3", collection="c")

        results = sqlite_client.query_prefix("", collection="c")
        assert len(results) == 3


class TestSQLiteConcurrency:
    """Thread safety under concurrent access."""

    def test_concurrent_writes_no_corruption(self, sqlite_client):
        errors = []

        def writer(thread_id):
            try:
                for i in range(50):
                    sqlite_client.add_node(
                        f"thread:{thread_id}:key:{i}",
                        f"data from thread {thread_id} item {i}",
                        collection="concurrent",
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent write errors: {errors}"

        results = sqlite_client.query_prefix("thread:", collection="concurrent", limit=500)
        assert len(results) == 250  # 5 threads x 50 keys


class TestSQLitePersistence:
    """Data survives client close and reopen."""

    def test_persistence_across_instances(self, tmp_dir):
        from synrix.sqlite_client import SynrixSQLiteClient
        db_path = os.path.join(tmp_dir, "persist.db")

        # Write with first instance
        client1 = SynrixSQLiteClient(db_path=db_path)
        client1.add_node("persist:key", '{"important": true}', collection="data")
        client1.close()

        # Read with second instance
        client2 = SynrixSQLiteClient(db_path=db_path)
        results = client2.query_prefix("persist:", collection="data")
        assert len(results) == 1
        assert results[0]["payload"]["data"] == '{"important": true}'
        client2.close()


class TestSQLiteCollections:
    """Collection management."""

    def test_create_collection(self, sqlite_client):
        result = sqlite_client.create_collection("test_col")
        assert result is True

    def test_collection_isolation(self, sqlite_client):
        sqlite_client.add_node("key", "in_col_a", collection="col_a")
        sqlite_client.add_node("key", "in_col_b", collection="col_b")

        a = sqlite_client.query_prefix("key", collection="col_a")
        b = sqlite_client.query_prefix("key", collection="col_b")

        assert len(a) == 1
        assert len(b) == 1
        assert a[0]["payload"]["data"] == "in_col_a"
        assert b[0]["payload"]["data"] == "in_col_b"
