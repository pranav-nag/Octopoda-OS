"""
SYNRIX Embeddings — Local Semantic Encoding
=============================================
Lazy-loading wrapper around sentence-transformers for offline embeddings.
Falls back gracefully when the library is not installed.

Default model: BAAI/bge-small-en-v1.5 (33M params, 384-dim, MIT license)
— optimised for asymmetric query-to-document retrieval.

Override with env var OCTOPODA_EMBEDDING_MODEL or pass model_name to get().

Usage:
    from synrix.embeddings import EmbeddingModel

    model = EmbeddingModel.get()  # None if sentence-transformers missing
    if model:
        blob = model.encode("hello world")       # -> bytes (384-dim float32)
        vec  = model.decode(blob)                 # -> np.ndarray
"""

import os
import struct
from typing import Optional

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"


class EmbeddingModel:
    """Singleton wrapper for CPU-only local embeddings (default: bge-small-en-v1.5)."""

    _instance: Optional["EmbeddingModel"] = None

    def __init__(self):
        self._model = None
        self._dim = 384
        self._model_name: str = ""

    @classmethod
    def get(cls, model_name: Optional[str] = None) -> Optional["EmbeddingModel"]:
        """Get the singleton embedding model, or None if deps are missing.

        Args:
            model_name: Override the default model. Can also be set via
                        the OCTOPODA_EMBEDDING_MODEL environment variable.
        """
        if cls._instance is not None:
            return cls._instance

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            return None

        if not _HAS_NUMPY:
            return None

        chosen = (
            model_name
            or os.environ.get("OCTOPODA_EMBEDDING_MODEL")
            or DEFAULT_MODEL
        )

        instance = cls()
        instance._model = SentenceTransformer(chosen, device="cpu")
        instance._model_name = chosen
        instance._dim = instance._model.get_sentence_embedding_dimension()
        cls._instance = instance
        return instance

    @classmethod
    def reset(cls):
        """Reset singleton (for testing)."""
        cls._instance = None

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def model_name(self) -> str:
        return self._model_name

    def encode(self, text: str) -> bytes:
        """Encode text to a normalized 384-dim float32 BLOB."""
        vec = self._model.encode(text, normalize_embeddings=True)
        return struct.pack(f"{len(vec)}f", *vec.tolist())

    def encode_batch(self, texts: list) -> list:
        """Encode multiple texts at once. Returns list of bytes."""
        vecs = self._model.encode(texts, normalize_embeddings=True)
        return [
            struct.pack(f"{len(v)}f", *v.tolist())
            for v in vecs
        ]

    def decode(self, blob: bytes) -> "np.ndarray":
        """Decode a BLOB back to a numpy array."""
        return np.frombuffer(blob, dtype=np.float32).copy()

    def text_to_vector(self, text: str) -> "np.ndarray":
        """Encode text directly to a numpy array (for search queries)."""
        return self._model.encode(text, normalize_embeddings=True)
