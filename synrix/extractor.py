"""
SYNRIX Entity Extractor — NLP-Powered Knowledge Extraction
============================================================
Uses spaCy for named entity recognition and dependency parsing
to extract entities and subject-verb-object relationships from text.
Feeds into the knowledge graph automatically.

Falls back gracefully when spaCy is not installed.

Usage:
    from synrix.extractor import EntityExtractor

    extractor = EntityExtractor.get()  # None if spacy missing
    if extractor:
        result = extractor.extract("Alice works at Google in London")
        # result.entities == [("Alice", "PERSON"), ("Google", "ORG"), ("London", "GPE")]
        # result.relationships == [("Alice", "works_at", "Google"), ("Alice", "works_in", "London")]
"""

from dataclasses import dataclass, field
from typing import Optional, List, Tuple


@dataclass
class ExtractionResult:
    """Result of entity and relationship extraction."""
    entities: List[Tuple[str, str]] = field(default_factory=list)
    relationships: List[Tuple[str, str, str]] = field(default_factory=list)


class EntityExtractor:
    """Singleton spaCy-based entity and relationship extractor."""

    _instance: Optional["EntityExtractor"] = None

    def __init__(self):
        self._nlp = None

    @classmethod
    def get(cls) -> Optional["EntityExtractor"]:
        """Get the singleton extractor, or None if spaCy/model missing."""
        if cls._instance is not None:
            return cls._instance

        try:
            import spacy
        except ImportError:
            return None

        try:
            nlp = spacy.load("en_core_web_sm")
        except OSError:
            return None

        instance = cls()
        instance._nlp = nlp
        cls._instance = instance
        return instance

    @classmethod
    def reset(cls):
        """Reset singleton (for testing)."""
        cls._instance = None

    def extract(self, text: str) -> ExtractionResult:
        """Extract entities and relationships from text."""
        if not text or not isinstance(text, str):
            return ExtractionResult()

        doc = self._nlp(text)

        entities = [
            (ent.text, ent.label_)
            for ent in doc.ents
        ]

        relationships = self._extract_svo_triples(doc)

        return ExtractionResult(entities=entities, relationships=relationships)

    def _extract_svo_triples(self, doc) -> List[Tuple[str, str, str]]:
        """Extract subject-verb-object triples from dependency parse."""
        triples = []
        seen = set()

        for token in doc:
            if token.dep_ not in ("nsubj", "nsubjpass"):
                continue

            subject = token.text
            verb = token.head

            # Skip if verb is not actually a verb
            if verb.pos_ not in ("VERB", "AUX"):
                continue

            for child in verb.children:
                obj = None
                relation = verb.lemma_

                if child.dep_ in ("dobj", "attr", "oprd"):
                    obj = child.text
                elif child.dep_ == "prep":
                    # Handle prepositional objects: "works at Google"
                    for pobj in child.children:
                        if pobj.dep_ == "pobj":
                            relation = f"{verb.lemma_}_{child.text}"
                            obj = pobj.text
                            break

                if obj and (subject, relation, obj) not in seen:
                    seen.add((subject, relation, obj))
                    triples.append((subject, relation, obj))

        return triples

    def extract_text_from_value(self, value) -> str:
        """Extract searchable text from a memory value (dict or string)."""
        if isinstance(value, str):
            return value

        if isinstance(value, dict):
            parts = []
            for key in ("value", "text", "content", "description", "message"):
                v = value.get(key)
                if isinstance(v, str):
                    parts.append(v)
                elif isinstance(v, dict):
                    # Recursively extract text from nested dicts
                    for inner_v in v.values():
                        if isinstance(inner_v, str):
                            parts.append(inner_v)
            return " ".join(parts) if parts else str(value)

        return str(value)
