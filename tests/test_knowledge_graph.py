"""
Tests for the SQLite-based knowledge graph (entities + relationships).
"""

import os
import json
import pytest


class TestEntityCRUD:
    """Test entity creation, update, and querying."""

    def test_upsert_entity(self, sqlite_client):
        sqlite_client.create_collection("test")
        eid = sqlite_client.upsert_entity("Alice", "PERSON", collection="test")
        assert eid is not None
        assert isinstance(eid, int)

    def test_upsert_same_entity_increments_count(self, sqlite_client):
        sqlite_client.create_collection("test")
        eid1 = sqlite_client.upsert_entity("Alice", "PERSON", collection="test")
        eid2 = sqlite_client.upsert_entity("Alice", "PERSON", collection="test")

        assert eid1 == eid2  # Same entity, same ID
        entity = sqlite_client.query_entity("Alice", collection="test")
        assert entity is not None
        assert entity["mention_count"] == 2

    def test_different_types_different_entities(self, sqlite_client):
        sqlite_client.create_collection("test")
        eid1 = sqlite_client.upsert_entity("Apple", "ORG", collection="test")
        eid2 = sqlite_client.upsert_entity("Apple", "PRODUCT", collection="test")
        assert eid1 != eid2

    def test_query_entity_not_found(self, sqlite_client):
        sqlite_client.create_collection("test")
        result = sqlite_client.query_entity("nonexistent", collection="test")
        assert result is None

    def test_list_entities(self, sqlite_client):
        sqlite_client.create_collection("test")
        sqlite_client.upsert_entity("Alice", "PERSON", collection="test")
        sqlite_client.upsert_entity("Bob", "PERSON", collection="test")
        sqlite_client.upsert_entity("Google", "ORG", collection="test")

        all_entities = sqlite_client.list_entities(collection="test")
        assert len(all_entities) == 3

    def test_list_entities_by_type(self, sqlite_client):
        sqlite_client.create_collection("test")
        sqlite_client.upsert_entity("Alice", "PERSON", collection="test")
        sqlite_client.upsert_entity("Bob", "PERSON", collection="test")
        sqlite_client.upsert_entity("Google", "ORG", collection="test")

        people = sqlite_client.list_entities(collection="test", entity_type="PERSON")
        assert len(people) == 2
        names = {e["name"] for e in people}
        assert names == {"Alice", "Bob"}


class TestRelationships:
    """Test relationship creation and graph queries."""

    def test_add_relationship(self, sqlite_client):
        sqlite_client.create_collection("test")
        eid1 = sqlite_client.upsert_entity("Alice", "PERSON", collection="test")
        eid2 = sqlite_client.upsert_entity("Google", "ORG", collection="test")

        rid = sqlite_client.add_relationship(eid1, eid2, "works_at", collection="test")
        assert rid is not None

    def test_query_entity_with_relationships(self, sqlite_client):
        sqlite_client.create_collection("test")
        eid1 = sqlite_client.upsert_entity("Alice", "PERSON", collection="test")
        eid2 = sqlite_client.upsert_entity("Google", "ORG", collection="test")
        eid3 = sqlite_client.upsert_entity("London", "GPE", collection="test")

        sqlite_client.add_relationship(eid1, eid2, "works_at", collection="test")
        sqlite_client.add_relationship(eid1, eid3, "lives_in", collection="test")

        result = sqlite_client.query_entity("Alice", collection="test")
        assert result is not None
        assert len(result["relationships"]) == 2

        rels = {r["relation"] for r in result["relationships"]}
        assert "works_at" in rels
        assert "lives_in" in rels

    def test_relationship_bidirectional_query(self, sqlite_client):
        sqlite_client.create_collection("test")
        eid1 = sqlite_client.upsert_entity("Alice", "PERSON", collection="test")
        eid2 = sqlite_client.upsert_entity("Google", "ORG", collection="test")
        sqlite_client.add_relationship(eid1, eid2, "works_at", collection="test")

        # Query from the target side
        result = sqlite_client.query_entity("Google", collection="test")
        assert result is not None
        assert len(result["relationships"]) == 1
        assert result["relationships"][0]["target"] == "Alice"
        assert result["relationships"][0].get("direction") == "incoming"

    def test_duplicate_relationship_updates(self, sqlite_client):
        sqlite_client.create_collection("test")
        eid1 = sqlite_client.upsert_entity("Alice", "PERSON", collection="test")
        eid2 = sqlite_client.upsert_entity("Google", "ORG", collection="test")

        rid1 = sqlite_client.add_relationship(eid1, eid2, "works_at", collection="test", confidence=0.8)
        rid2 = sqlite_client.add_relationship(eid1, eid2, "works_at", collection="test", confidence=0.95)

        assert rid1 == rid2  # Same relationship, updated

        result = sqlite_client.query_entity("Alice", collection="test")
        assert len(result["relationships"]) == 1
        assert result["relationships"][0]["confidence"] == 0.95


class TestKnowledgeGraphBackend:
    """Test knowledge graph through SynrixAgentBackend."""

    def test_add_and_query_entity(self, agent_backend):
        eid = agent_backend.add_entity("TestEntity", "CONCEPT")
        assert eid is not None

        result = agent_backend.query_entity("TestEntity")
        assert result is not None
        assert result["name"] == "TestEntity"
        assert result["entity_type"] == "CONCEPT"

    def test_add_relationship_through_backend(self, agent_backend):
        eid1 = agent_backend.add_entity("Alice", "PERSON")
        eid2 = agent_backend.add_entity("Acme", "ORG")
        rid = agent_backend.add_relationship(eid1, eid2, "works_at")
        assert rid is not None

    def test_list_entities_through_backend(self, agent_backend):
        agent_backend.add_entity("A", "TYPE1")
        agent_backend.add_entity("B", "TYPE2")
        entities = agent_backend.list_entities()
        assert len(entities) >= 2

    def test_delete_collection_clears_entities(self, sqlite_client):
        sqlite_client.create_collection("temp_col")
        sqlite_client.upsert_entity("X", "TYPE", collection="temp_col")
        sqlite_client.delete_collection("temp_col")
        entities = sqlite_client.list_entities(collection="temp_col")
        assert len(entities) == 0
