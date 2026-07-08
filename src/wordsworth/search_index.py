"""The search seam (driver/protocol pattern) and an in-memory test double.

The pipeline depends on the `SearchIndex` protocol, never on OpenSearch directly.
`hybrid_search` returns an RRF-fused recall set (with vectors); the final ranking
(zeef cosine) is applied by the hybrid orchestration, not here."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from zeef.similarity import cosine

from .rrf import fuse_ranked_ids


@dataclass
class Hit:
    document_id: str
    score: float
    object_key: str | None = None
    vector: list[float] | None = None


@runtime_checkable
class SearchIndex(Protocol):
    def ensure_ready(self) -> None: ...
    def index(self, document_id: str, text: str, object_key: str,
              vector: list[float] | None = None) -> None: ...
    def search(self, query: str, size: int = 10) -> list[Hit]: ...
    def hybrid_search(self, query: str, query_vector: list[float],
                      recall: int = 50) -> list[Hit]: ...


def _terms(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


@dataclass
class InMemoryIndex:
    """Term-overlap BM25 stand-in + cosine kNN — enough to prove wiring in tests."""

    _docs: dict[str, tuple[str, str, list[float] | None]] = field(default_factory=dict)

    def ensure_ready(self) -> None:
        pass

    def index(self, document_id, text, object_key, vector=None) -> None:
        self._docs[document_id] = (text, object_key, vector)  # idempotent upsert

    def _lexical(self, query: str) -> list[tuple[str, float]]:
        q = set(_terms(query))
        scored = []
        for doc_id, (text, _key, _vec) in self._docs.items():
            score = float(sum(1 for t in _terms(text) if t in q))
            if score > 0:
                scored.append((doc_id, score))
        scored.sort(key=lambda p: p[1], reverse=True)
        return scored

    def search(self, query: str, size: int = 10) -> list[Hit]:
        return [
            Hit(doc_id, score, self._docs[doc_id][1])
            for doc_id, score in self._lexical(query)[:size]
        ]

    def hybrid_search(self, query, query_vector, recall: int = 50) -> list[Hit]:
        lexical_ids = [doc_id for doc_id, _ in self._lexical(query)]
        knn = sorted(
            ((doc_id, cosine(query_vector, vec))
             for doc_id, (_t, _k, vec) in self._docs.items() if vec),
            key=lambda p: p[1], reverse=True,
        )
        knn_ids = [doc_id for doc_id, _ in knn]
        fused = fuse_ranked_ids([lexical_ids, knn_ids])[:recall]
        return [Hit(d, 0.0, self._docs[d][1], self._docs[d][2]) for d in fused]
