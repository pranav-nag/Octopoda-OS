"""
Tests for temporal awareness (versioning and history).
"""

import os
import json
import time
import pytest


class TestTemporalVersioning:
    """Test that updating a node creates a new version and invalidates the old."""

    def test_first_write_has_version_one(self, sqlite_client):
        sqlite_client.create_collection("test")
        sqlite_client.add_node("key1", '{"value": "first"}', collection="test")

        history = sqlite_client.get_history("key1", collection="test")
        assert len(history) == 1
        assert history[0]["version"] == 1
        assert history[0]["valid_until"] is None or history[0]["valid_until"] == 0

    def test_update_creates_new_version(self, sqlite_client):
        sqlite_client.create_collection("test")
        sqlite_client.add_node("key1", '{"value": "v1"}', collection="test")
        sqlite_client.add_node("key1", '{"value": "v2"}', collection="test")

        history = sqlite_client.get_history("key1", collection="test")
        assert len(history) == 2
        # History is ordered by version DESC
        assert history[0]["version"] == 2
        assert history[1]["version"] == 1

    def test_old_version_invalidated(self, sqlite_client):
        sqlite_client.create_collection("test")
        sqlite_client.add_node("key1", '{"value": "old"}', collection="test")
        sqlite_client.add_node("key1", '{"value": "new"}', collection="test")

        history = sqlite_client.get_history("key1", collection="test")
        # Version 1 should be invalidated (valid_until is set)
        old = [h for h in history if h["version"] == 1][0]
        assert old["valid_until"] is not None and old["valid_until"] > 0

        # Version 2 should be current (valid_until is None or 0)
        current = [h for h in history if h["version"] == 2][0]
        assert current["valid_until"] is None or current["valid_until"] == 0

    def test_query_prefix_returns_only_current(self, sqlite_client):
        sqlite_client.create_collection("test")
        sqlite_client.add_node("key1", '{"value": "v1"}', collection="test")
        sqlite_client.add_node("key1", '{"value": "v2"}', collection="test")
        sqlite_client.add_node("key1", '{"value": "v3"}', collection="test")

        results = sqlite_client.query_prefix("key1", collection="test")
        # Should only return the current version
        assert len(results) == 1
        data = json.loads(results[0]["payload"]["data"])
        assert data["value"] == "v3"

    def test_three_versions(self, sqlite_client):
        sqlite_client.create_collection("test")
        sqlite_client.add_node("key1", '"alpha"', collection="test")
        sqlite_client.add_node("key1", '"beta"', collection="test")
        sqlite_client.add_node("key1", '"gamma"', collection="test")

        history = sqlite_client.get_history("key1", collection="test")
        assert len(history) == 3
        versions = [h["version"] for h in history]
        assert versions == [3, 2, 1]

    def test_valid_from_is_set(self, sqlite_client):
        sqlite_client.create_collection("test")
        before = time.time()
        sqlite_client.add_node("key1", '{"value": "hello"}', collection="test")
        after = time.time()

        history = sqlite_client.get_history("key1", collection="test")
        assert len(history) == 1
        assert history[0]["valid_from"] is not None
        assert before <= history[0]["valid_from"] <= after

    def test_different_keys_independent(self, sqlite_client):
        sqlite_client.create_collection("test")
        sqlite_client.add_node("key_a", '"a1"', collection="test")
        sqlite_client.add_node("key_a", '"a2"', collection="test")
        sqlite_client.add_node("key_b", '"b1"', collection="test")

        history_a = sqlite_client.get_history("key_a", collection="test")
        history_b = sqlite_client.get_history("key_b", collection="test")
        assert len(history_a) == 2
        assert len(history_b) == 1

    def test_node_count_excludes_old_versions(self, sqlite_client):
        sqlite_client.create_collection("test")
        sqlite_client.add_node("key1", '"v1"', collection="test")
        sqlite_client.add_node("key1", '"v2"', collection="test")
        sqlite_client.add_node("key2", '"data"', collection="test")

        count = sqlite_client.node_count(collection="test")
        # Should be 2 (key1 current + key2), not 3
        assert count == 2


class TestTemporalBackend:
    """Test temporal features through SynrixAgentBackend."""

    def test_get_history_through_backend(self, agent_backend):
        agent_backend.write("test:key1", {"value": "version_one"})
        agent_backend.write("test:key1", {"value": "version_two"})

        history = agent_backend.get_history("test:key1")
        assert len(history) == 2
        values = [h["data"]["value"]["value"] for h in history if "value" in h.get("data", {}).get("value", {})]
        assert "version_one" in str(values) or "version_two" in str(values)
