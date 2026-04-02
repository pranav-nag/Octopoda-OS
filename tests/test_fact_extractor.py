"""
Tests for Ollama-based fact extraction and fact embedding search.

Tests that require Ollama are skipped if it's not running.
Tests that require sentence-transformers are skipped if not installed.
"""

import struct
import time
import pytest

np = pytest.importorskip("numpy")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ollama_available():
    """Check if Ollama is running locally."""
    try:
        import requests
        resp = requests.get("http://localhost:11434/api/tags", timeout=2)
        return resp.status_code == 200
    except Exception:
        return False


skip_no_ollama = pytest.mark.skipif(
    not _ollama_available(), reason="Ollama not running"
)


# ---------------------------------------------------------------------------
# Fact extractor unit tests
# ---------------------------------------------------------------------------

class TestFactExtractorParsing:
    """Test the JSON parsing logic (no Ollama needed)."""

    def test_parse_valid_json_array(self):
        from synrix.fact_extractor import FactExtractor
        facts = FactExtractor._parse_facts('["fact one", "fact two"]')
        assert facts == ["fact one", "fact two"]

    def test_parse_json_with_surrounding_text(self):
        from synrix.fact_extractor import FactExtractor
        raw = 'Here are the facts:\n["User is vegetarian", "User lives in London"]\n'
        facts = FactExtractor._parse_facts(raw)
        assert len(facts) == 2
        assert "User is vegetarian" in facts

    def test_parse_invalid_json(self):
        from synrix.fact_extractor import FactExtractor
        facts = FactExtractor._parse_facts("not json at all")
        assert facts == []

    def test_parse_empty_array(self):
        from synrix.fact_extractor import FactExtractor
        facts = FactExtractor._parse_facts("[]")
        assert facts == []

    def test_parse_filters_non_strings(self):
        from synrix.fact_extractor import FactExtractor
        facts = FactExtractor._parse_facts('[123, "valid fact", null, ""]')
        assert facts == ["valid fact"]


class TestFactExtractorShortText:
    """Test that very short text is returned as-is without calling Ollama."""

    def test_empty_text(self):
        from synrix.fact_extractor import FactExtractor, FactExtractionResult
        # Create instance manually to test without Ollama
        extractor = FactExtractor()
        extractor._available = True
        extractor._ollama_url = "http://localhost:11434"
        extractor._model_name = "llama3.2"

        result = extractor.extract_facts("")
        assert result.facts == []
        assert not result.used_ollama

    def test_short_text_skipped(self):
        from synrix.fact_extractor import FactExtractor
        extractor = FactExtractor()
        extractor._available = True
        extractor._ollama_url = "http://localhost:11434"
        extractor._model_name = "llama3.2"

        result = extractor.extract_facts("hi there")
        assert result.facts == ["hi there"]
        assert not result.used_ollama


@skip_no_ollama
class TestFactExtractorWithOllama:
    """Integration tests that actually call Ollama."""

    def test_extract_multiple_facts(self):
        from synrix.fact_extractor import FactExtractor
        FactExtractor.reset()
        extractor = FactExtractor.get()
        assert extractor is not None

        result = extractor.extract_facts(
            "I am a vegetarian living in London and I work at Google"
        )
        assert result.used_ollama
        assert len(result.facts) >= 2
        assert result.extraction_time_ms > 0

    def test_extract_single_fact(self):
        from synrix.fact_extractor import FactExtractor
        FactExtractor.reset()
        extractor = FactExtractor.get()

        result = extractor.extract_facts("The user prefers dark mode")
        assert result.used_ollama
        assert len(result.facts) >= 1

    def test_facts_are_strings(self):
        from synrix.fact_extractor import FactExtractor
        FactExtractor.reset()
        extractor = FactExtractor.get()

        result = extractor.extract_facts(
            "Alice enjoys hiking and cooking Italian food"
        )
        for fact in result.facts:
            assert isinstance(fact, str)
            assert len(fact) > 0


# ---------------------------------------------------------------------------
# Fact embedding storage tests (no Ollama needed)
# ---------------------------------------------------------------------------

class TestFactEmbeddingStorage:
    """Test storing and searching fact embeddings in SQLite."""

    def test_store_and_search_fact_embeddings(self, sqlite_client):
        """Fact embeddings should be found by semantic search."""
        sqlite_client.create_collection("test")

        # Store a node
        node_id = sqlite_client.add_node("key1", '{"value": "raw text"}', collection="test")

        # Store fact embeddings for that node
        vec1 = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        vec2 = np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)
        facts = [
            {"text": "fact about food", "embedding": struct.pack("4f", *vec1.tolist())},
            {"text": "fact about location", "embedding": struct.pack("4f", *vec2.tolist())},
        ]
        count = sqlite_client.add_fact_embeddings(node_id, "key1", facts, collection="test")
        assert count == 2

        # Search should find via fact embeddings
        query = np.array([0.95, 0.05, 0.0, 0.0], dtype=np.float32)
        query_blob = struct.pack("4f", *query.tolist())
        results = sqlite_client.semantic_search(query_blob, collection="test")
        assert len(results) >= 1
        assert results[0]["payload"]["name"] == "key1"
        assert "matched_fact" in results[0]
        assert results[0]["matched_fact"] == "fact about food"

    def test_fact_search_returns_best_score_per_memory(self, sqlite_client):
        """When a memory has multiple facts, return the best-scoring one."""
        sqlite_client.create_collection("test")
        node_id = sqlite_client.add_node("bio", '{"value": "bio data"}', collection="test")

        vec_food = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        vec_loc = np.array([0.0, 0.0, 1.0, 0.0], dtype=np.float32)
        facts = [
            {"text": "User is vegetarian (food)", "embedding": struct.pack("4f", *vec_food.tolist())},
            {"text": "User lives in London (location)", "embedding": struct.pack("4f", *vec_loc.tolist())},
        ]
        sqlite_client.add_fact_embeddings(node_id, "bio", facts, collection="test")

        # Query about food → should match food fact
        query = np.array([0.9, 0.1, 0.0, 0.0], dtype=np.float32)
        query_blob = struct.pack("4f", *query.tolist())
        results = sqlite_client.semantic_search(query_blob, collection="test")
        assert results[0]["matched_fact"] == "User is vegetarian (food)"

        # Query about location → should match location fact
        query2 = np.array([0.0, 0.1, 0.9, 0.0], dtype=np.float32)
        query_blob2 = struct.pack("4f", *query2.tolist())
        results2 = sqlite_client.semantic_search(query_blob2, collection="test")
        assert results2[0]["matched_fact"] == "User lives in London (location)"

    def test_fact_embeddings_replaced_on_update(self, sqlite_client):
        """Updating a memory should replace its fact embeddings."""
        sqlite_client.create_collection("test")
        node_id1 = sqlite_client.add_node("key1", '{"value": "v1"}', collection="test")

        vec = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        blob = struct.pack("4f", *vec.tolist())
        sqlite_client.add_fact_embeddings(node_id1, "key1", [{"text": "old fact", "embedding": blob}], collection="test")

        # Update node → new version
        node_id2 = sqlite_client.add_node("key1", '{"value": "v2"}', collection="test")

        # Replace facts
        vec2 = np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)
        blob2 = struct.pack("4f", *vec2.tolist())
        sqlite_client.add_fact_embeddings(node_id2, "key1", [{"text": "new fact", "embedding": blob2}], collection="test")

        # Search should only find new fact (old node is invalidated)
        query = np.array([0.0, 0.9, 0.1, 0.0], dtype=np.float32)
        query_blob = struct.pack("4f", *query.tolist())
        results = sqlite_client.semantic_search(query_blob, collection="test")
        assert len(results) >= 1
        assert results[0]["matched_fact"] == "new fact"

    def test_falls_back_to_node_embeddings(self, sqlite_client):
        """Without fact embeddings, search should use nodes.embedding."""
        sqlite_client.create_collection("test")

        vec = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        blob = struct.pack("4f", *vec.tolist())
        sqlite_client.add_node("key1", '{"value": "data"}', collection="test", embedding=blob)

        # No fact_embeddings stored → should fall back to node embedding
        query = np.array([0.95, 0.05, 0.0, 0.0], dtype=np.float32)
        query_blob = struct.pack("4f", *query.tolist())
        results = sqlite_client.semantic_search(query_blob, collection="test")
        assert len(results) >= 1
        assert results[0]["payload"]["name"] == "key1"
        assert "matched_fact" not in results[0]  # no fact matching used

    def test_delete_collection_clears_fact_embeddings(self, sqlite_client):
        """Deleting a collection should also clear its fact embeddings."""
        sqlite_client.create_collection("test")
        node_id = sqlite_client.add_node("key1", '{"value": "data"}', collection="test")

        vec = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        blob = struct.pack("4f", *vec.tolist())
        sqlite_client.add_fact_embeddings(node_id, "key1", [{"text": "fact", "embedding": blob}], collection="test")

        sqlite_client.delete_collection("test")

        # Recreate and search — should be empty
        sqlite_client.create_collection("test")
        query_blob = struct.pack("4f", *vec.tolist())
        results = sqlite_client.semantic_search(query_blob, collection="test")
        assert results == []
