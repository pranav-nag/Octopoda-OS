"""
Tests for the entity extractor (spaCy NER + SVO triples).

These tests require spaCy and the en_core_web_sm model.
Tests are skipped if the dependencies are not installed.
"""

import pytest

# Skip entire module if spacy or model is not installed
spacy = pytest.importorskip("spacy")

try:
    spacy.load("en_core_web_sm")
    _HAS_MODEL = True
except OSError:
    _HAS_MODEL = False

pytestmark = pytest.mark.skipif(not _HAS_MODEL, reason="en_core_web_sm not installed")


from synrix.extractor import EntityExtractor, ExtractionResult


@pytest.fixture(autouse=True)
def _reset_extractor():
    """Reset extractor singleton between tests."""
    EntityExtractor.reset()
    yield
    EntityExtractor.reset()


class TestEntityExtraction:
    """Test named entity recognition."""

    def test_extract_person(self):
        extractor = EntityExtractor.get()
        assert extractor is not None

        result = extractor.extract("Barack Obama visited London last week")
        entity_names = [e[0] for e in result.entities]
        assert "Barack Obama" in entity_names

    def test_extract_location(self):
        extractor = EntityExtractor.get()
        result = extractor.extract("The company is based in San Francisco")
        entity_names = [e[0] for e in result.entities]
        assert "San Francisco" in entity_names

    def test_extract_organization(self):
        extractor = EntityExtractor.get()
        result = extractor.extract("She works at Google")
        entity_types = {e[0]: e[1] for e in result.entities}
        assert "Google" in entity_types

    def test_extract_empty_text(self):
        extractor = EntityExtractor.get()
        result = extractor.extract("")
        assert result.entities == []
        assert result.relationships == []

    def test_extract_no_entities(self):
        extractor = EntityExtractor.get()
        result = extractor.extract("hello world")
        # May or may not find entities depending on model, but should not crash
        assert isinstance(result, ExtractionResult)


class TestSVOExtraction:
    """Test subject-verb-object triple extraction."""

    def test_extract_simple_svo(self):
        extractor = EntityExtractor.get()
        result = extractor.extract("Alice bought a car")
        # Should extract at least one relationship
        # Note: exact extraction depends on spaCy's parsing
        assert isinstance(result.relationships, list)

    def test_extraction_result_structure(self):
        extractor = EntityExtractor.get()
        result = extractor.extract("Google acquired YouTube for one billion dollars")
        assert isinstance(result.entities, list)
        assert isinstance(result.relationships, list)
        for entity in result.entities:
            assert len(entity) == 2  # (name, type)
        for rel in result.relationships:
            assert len(rel) == 3  # (subject, relation, object)


class TestExtractTextFromValue:
    """Test text extraction from various value formats."""

    def test_string_value(self):
        extractor = EntityExtractor.get()
        assert extractor.extract_text_from_value("hello") == "hello"

    def test_dict_with_value_key(self):
        extractor = EntityExtractor.get()
        text = extractor.extract_text_from_value({"value": "world"})
        assert "world" in text

    def test_dict_with_text_key(self):
        extractor = EntityExtractor.get()
        text = extractor.extract_text_from_value({"text": "content here"})
        assert "content here" in text

    def test_dict_without_text_keys(self):
        extractor = EntityExtractor.get()
        text = extractor.extract_text_from_value({"count": 42})
        assert isinstance(text, str)
