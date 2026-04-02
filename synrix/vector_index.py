"""
Synrix Vector Index — Cached In-Memory Search
==============================================
Provides fast vector similarity search with two backends:
  1. FAISS (if installed) — SIMD-optimized, 10-100x faster at scale
  2. NumPy fallback — cached matrix, no per-search SQLite reload

Key design:
  - Index is built lazily on first search
  - Invalidated when new writes happen (dirty flag)
  - Rebuilt incrementally from SQLite only when needed
  - Thread-safe with read-write locking
  - Zero required dependencies beyond numpy
"""

import threading
from typing import List, Dict, Any, Optional, Tuple

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    import faiss
    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False


class VectorIndex:
    """
    In-memory vector index for a single collection.

    Caches embeddings and metadata so searches don't reload from SQLite
    every time. Uses FAISS if available, numpy brute-force otherwise.
    """

    def __init__(self, dim: int = 384):
        self.dim = dim
        self._lock = threading.RLock()

        # Stored data
        self._ids: List[int] = []
        self._names: List[str] = []
        self._datas: List[str] = []
        self._types: List[str] = []
        self._vectors: Optional[Any] = None  # numpy array or None

        # FAISS index (if available)
        self._faiss_index: Optional[Any] = None

        # State tracking
        self._count = 0
        self._dirty = True
        self._version = 0

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def mark_dirty(self):
        """Mark index as needing rebuild (called after writes)."""
        with self._lock:
            self._dirty = True
            self._version += 1

    def build(self, ids: List[int], names: List[str], datas: List[str],
              types: List[str], embeddings: List[Any]):
        """Build the full index from a list of vectors + metadata."""
        with self._lock:
            if not embeddings:
                self._ids = []
                self._names = []
                self._datas = []
                self._types = []
                self._vectors = None
                self._faiss_index = None
                self._count = 0
                self._dirty = False
                return

            self._ids = list(ids)
            self._names = list(names)
            self._datas = list(datas)
            self._types = list(types)

            matrix = np.stack(embeddings).astype(np.float32)

            # Normalize all vectors for cosine similarity via inner product
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            matrix = matrix / norms

            self._vectors = matrix
            self._count = len(embeddings)

            # Build FAISS index if available
            if HAS_FAISS and self._count > 0:
                self._faiss_index = faiss.IndexFlatIP(self.dim)
                self._faiss_index.add(matrix)
            else:
                self._faiss_index = None

            self._dirty = False

    def search(self, query_vec: Any, limit: int = 10,
               threshold: float = 0.0) -> List[Dict[str, Any]]:
        """
        Search for nearest vectors.

        Returns list of {id, score, payload: {name, data, type}}
        """
        with self._lock:
            if self._count == 0 or self._vectors is None:
                return []

            # Normalize query
            query = query_vec.astype(np.float32).copy()
            norm = np.linalg.norm(query)
            if norm > 0:
                query /= norm

            if self._faiss_index is not None and HAS_FAISS:
                return self._search_faiss(query, limit, threshold)
            else:
                return self._search_numpy(query, limit, threshold)

    def _search_faiss(self, query: Any, limit: int,
                      threshold: float) -> List[Dict[str, Any]]:
        """Search using FAISS — fast SIMD-optimized inner product."""
        # FAISS needs 2D input
        query_2d = query.reshape(1, -1)
        # Search for more than limit in case some are below threshold
        k = min(limit * 2, self._count)
        scores, indices = self._faiss_index.search(query_2d, k)

        results = []
        for i in range(k):
            idx = int(indices[0][i])
            if idx < 0:  # FAISS returns -1 for empty slots
                continue
            score = float(scores[0][i])
            if score < threshold:
                continue
            results.append({
                "id": self._ids[idx],
                "score": score,
                "payload": {
                    "name": self._names[idx],
                    "data": self._datas[idx],
                    "type": self._types[idx],
                },
            })
            if len(results) >= limit:
                break

        return results

    def _search_numpy(self, query: Any, limit: int,
                      threshold: float) -> List[Dict[str, Any]]:
        """Search using cached numpy matrix — no SQLite reload."""
        scores = np.dot(self._vectors, query)

        # Get top-K indices efficiently
        if len(scores) <= limit * 2:
            ranked = np.argsort(scores)[::-1]
        else:
            # Use argpartition for O(n) partial sort — much faster than full sort at scale
            k = min(limit * 2, len(scores))
            top_k_idx = np.argpartition(scores, -k)[-k:]
            ranked = top_k_idx[np.argsort(scores[top_k_idx])[::-1]]

        results = []
        for idx in ranked:
            score = float(scores[idx])
            if score < threshold:
                break  # scores are sorted, rest will be lower
            results.append({
                "id": self._ids[idx],
                "score": score,
                "payload": {
                    "name": self._names[idx],
                    "data": self._datas[idx],
                    "type": self._types[idx],
                },
            })
            if len(results) >= limit:
                break

        return results

    def __len__(self):
        return self._count


class FactIndex:
    """
    In-memory index for fact_embeddings table.

    Similar to VectorIndex but groups results by parent node,
    returning the best-matching fact's score per memory.
    """

    def __init__(self, dim: int = 384):
        self.dim = dim
        self._lock = threading.RLock()

        # Stored data
        self._node_ids: List[int] = []
        self._node_names: List[str] = []
        self._fact_texts: List[str] = []
        self._datas: List[str] = []
        self._types: List[str] = []
        self._vectors: Optional[Any] = None

        self._faiss_index: Optional[Any] = None
        self._count = 0
        self._dirty = True
        self._version = 0

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def mark_dirty(self):
        with self._lock:
            self._dirty = True
            self._version += 1

    def build(self, node_ids: List[int], node_names: List[str],
              fact_texts: List[str], datas: List[str], types: List[str],
              embeddings: List[Any]):
        """Build the full fact index."""
        with self._lock:
            if not embeddings:
                self._node_ids = []
                self._node_names = []
                self._fact_texts = []
                self._datas = []
                self._types = []
                self._vectors = None
                self._faiss_index = None
                self._count = 0
                self._dirty = False
                return

            self._node_ids = list(node_ids)
            self._node_names = list(node_names)
            self._fact_texts = list(fact_texts)
            self._datas = list(datas)
            self._types = list(types)

            matrix = np.stack(embeddings).astype(np.float32)
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            matrix = matrix / norms

            self._vectors = matrix
            self._count = len(embeddings)

            if HAS_FAISS and self._count > 0:
                self._faiss_index = faiss.IndexFlatIP(self.dim)
                self._faiss_index.add(matrix)
            else:
                self._faiss_index = None

            self._dirty = False

    def search(self, query_vec: Any, limit: int = 10,
               threshold: float = 0.0) -> List[Dict[str, Any]]:
        """Search facts, group by parent node, return best score per memory."""
        with self._lock:
            if self._count == 0 or self._vectors is None:
                return []

            query = query_vec.astype(np.float32).copy()
            norm = np.linalg.norm(query)
            if norm > 0:
                query /= norm

            # Get raw scores for all facts
            if self._faiss_index is not None and HAS_FAISS:
                # Search for many results to ensure we find the best per node
                k = min(limit * 10, self._count)
                query_2d = query.reshape(1, -1)
                scores_arr, indices_arr = self._faiss_index.search(query_2d, k)
                score_index_pairs = [
                    (float(scores_arr[0][i]), int(indices_arr[0][i]))
                    for i in range(k)
                    if indices_arr[0][i] >= 0
                ]
            else:
                all_scores = np.dot(self._vectors, query)
                # Get top candidates
                k = min(limit * 10, len(all_scores))
                if k < len(all_scores):
                    top_k_idx = np.argpartition(all_scores, -k)[-k:]
                else:
                    top_k_idx = np.arange(len(all_scores))
                score_index_pairs = [
                    (float(all_scores[i]), int(i))
                    for i in top_k_idx
                ]

            # Group by node_name, keep best score per memory
            best_per_node: Dict[str, Dict] = {}
            for score_f, idx in score_index_pairs:
                if score_f < threshold:
                    continue
                name = self._node_names[idx]
                if name not in best_per_node or score_f > best_per_node[name]["score"]:
                    best_per_node[name] = {
                        "id": self._node_ids[idx],
                        "score": score_f,
                        "matched_fact": self._fact_texts[idx],
                        "payload": {
                            "name": name,
                            "data": self._datas[idx],
                            "type": self._types[idx],
                        },
                    }

            ranked = sorted(best_per_node.values(), key=lambda x: x["score"], reverse=True)
            return ranked[:limit]

    def __len__(self):
        return self._count
