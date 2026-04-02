"""
Tests for semantic vector search.

These tests require sentence-transformers and numpy.
Tests are skipped if the dependencies are not installed.
"""

import os
import json
import struct
import pytest


# Skip entire module if numpy is not installed
np = pytest.importorskip("numpy")


class TestEmbeddingStorage:
    """Test storing and retrieving embeddings in SQLite."""

    def test_store_node_with_embedding(self, sqlite_client):
        sqlite_client.create_collection("test")
        # Create a fake 4-dimensional embedding
        vec = np.array([0.5, 0.5, 0.5, 0.5], dtype=np.float32)
        blob = struct.pack(f"{len(vec)}f", *vec.tolist())

        node_id = sqlite_client.add_node(
            "key1", '{"value": "hello"}',
            collection="test", embedding=blob,
        )
        assert node_id is not None

    def test_store_node_without_embedding(self, sqlite_client):
        sqlite_client.create_collection("test")
        node_id = sqlite_client.add_node(
            "key1", '{"value": "hello"}', collection="test",
        )
        assert node_id is not None

    def test_semantic_search_with_fake_embeddings(self, sqlite_client):
        """Test semantic search using manually crafted embeddings."""
        sqlite_client.create_collection("test")

        # Create 3 nodes with different embeddings
        vec1 = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        vec2 = np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)
        vec3 = np.array([0.9, 0.1, 0.0, 0.0], dtype=np.float32)  # Similar to vec1

        for name, vec in [("doc_a", vec1), ("doc_b", vec2), ("doc_c", vec3)]:
            blob = struct.pack(f"{len(vec)}f", *vec.tolist())
            sqlite_client.add_node(name, f'{{"value": "{name}"}}', collection="test", embedding=blob)

        # Search with query similar to vec1
        query = np.array([0.95, 0.05, 0.0, 0.0], dtype=np.float32)
        query_blob = struct.pack(f"{len(query)}f", *query.tolist())

        results = sqlite_client.semantic_search(query_blob, collection="test", limit=3)
        assert len(results) >= 2

        # doc_a and doc_c should rank highest (most similar to query)
        names = [r["payload"]["name"] for r in results[:2]]
        assert "doc_a" in names
        assert "doc_c" in names

    def test_semantic_search_with_threshold(self, sqlite_client):
        """Test that threshold filters low-similarity results."""
        sqlite_client.create_collection("test")

        vec1 = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        vec2 = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32)  # Very different

        for name, vec in [("close", vec1), ("far", vec2)]:
            blob = struct.pack(f"{len(vec)}f", *vec.tolist())
            sqlite_client.add_node(name, f'{{"value": "{name}"}}', collection="test", embedding=blob)

        query = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        query_blob = struct.pack(f"{len(query)}f", *query.tolist())

        results = sqlite_client.semantic_search(query_blob, collection="test", threshold=0.5)
        names = [r["payload"]["name"] for r in results]
        assert "close" in names
        assert "far" not in names

    def test_semantic_search_empty_collection(self, sqlite_client):
        sqlite_client.create_collection("test")
        query = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        query_blob = struct.pack(f"{len(query)}f", *query.tolist())

        results = sqlite_client.semantic_search(query_blob, collection="test")
        assert results == []

    def test_semantic_search_ignores_nodes_without_embeddings(self, sqlite_client):
        sqlite_client.create_collection("test")

        # One with embedding, one without
        vec = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        blob = struct.pack(f"{len(vec)}f", *vec.tolist())
        sqlite_client.add_node("with_emb", '"has embedding"', collection="test", embedding=blob)
        sqlite_client.add_node("no_emb", '"no embedding"', collection="test")

        query_blob = struct.pack(f"{len(vec)}f", *vec.tolist())
        results = sqlite_client.semantic_search(query_blob, collection="test")
        assert len(results) == 1
        assert results[0]["payload"]["name"] == "with_emb"

    def test_semantic_search_limit(self, sqlite_client):
        sqlite_client.create_collection("test")

        for i in range(10):
            vec = np.random.randn(4).astype(np.float32)
            vec /= np.linalg.norm(vec)
            blob = struct.pack(f"{len(vec)}f", *vec.tolist())
            sqlite_client.add_node(f"doc_{i}", f'"doc {i}"', collection="test", embedding=blob)

        query = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        query_blob = struct.pack(f"{len(query)}f", *query.tolist())

        results = sqlite_client.semantic_search(query_blob, collection="test", limit=3)
        assert len(results) <= 3


class TestSemanticBackend:
    """Test semantic search through SynrixAgentBackend (requires sentence-transformers)."""

    def test_semantic_search_returns_list(self, agent_backend):
        """Semantic search should return a list (possibly empty if model not installed)."""
        result = agent_backend.semantic_search("hello world")
        assert isinstance(result, list)
