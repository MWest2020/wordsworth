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
    text: str | None = None  # de-identified index text (RAG sources)


@runtime_checkable
class SearchIndex(Protocol):
    def ensure_ready(self) -> None: ...
    def index(self, document_id: str, text: str, object_key: str,
              vector: list[float] | None = None,
              dossiers: list[str] | None = None) -> None: ...
    # ``only`` is the scope: a list of dossier ids, or None for every dossier.
    # None means "all" ONLY here, where it arrives from a caller that said so —
    # the API refuses a missing scope before it ever gets this far.
    def search(self, query: str, size: int = 10,
               only: list[str] | None = None) -> list[Hit]: ...
    def hybrid_search(self, query: str, query_vector: list[float],
                      recall: int = 50,
                      only: list[str] | None = None) -> list[Hit]: ...
    # Change ONLY the dossiers of a document. Re-indexing to move a membership
    # replaces the whole document, and a caller who forgets `vector=` silently
    # destroys the embedding — with no error, no audit record, and no way to
    # notice except results that are not there. That happened to 770 documents
    # on 2026-09-18. A membership change has no business touching the text or
    # the vector, so it does not get the chance.
    #: Returns whether the document was there. A membership change updates what
    #: exists; it does not index a document that never got through the straat —
    #: that is a different problem and hiding it here would bury it.
    def set_dossiers(self, document_id: str, dossiers: list[str]) -> bool: ...
    def has_object_key(self, object_key: str) -> bool:
        """Is a document with this content key already in the index? Used for
        idempotent ingest — the index is the source of truth for 'searchable',
        so recreating it correctly makes those documents eligible again."""
        ...


def _terms(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


@dataclass
class InMemoryIndex:
    """Term-overlap BM25 stand-in + cosine kNN — enough to prove wiring in tests."""

    _docs: dict[str, tuple[str, str, list[float] | None]] = field(default_factory=dict)
    #: document id -> the dossiers it belongs to. A document in two dossiers is
    #: ONE entry with two values, not two entries.
    _dossiers: dict[str, set[str]] = field(default_factory=dict)

    def ensure_ready(self) -> None:
        pass

    def index(self, document_id, text, object_key, vector=None,
              dossiers=None) -> None:
        self._docs[document_id] = (text, object_key, vector)  # idempotent upsert
        self._dossiers[document_id] = set(dossiers or ())

    # Change ONLY the dossiers of a document. Re-indexing to move a membership
    # replaces the whole document, and a caller who forgets `vector=` silently
    # destroys the embedding — with no error, no audit record, and no way to
    # notice except results that are not there. That happened to 770 documents
    # on 2026-09-18. A membership change has no business touching the text or
    # the vector, so it does not get the chance.
    #: Returns whether the document was there. A membership change updates what
    #: exists; it does not index a document that never got through the straat —
    #: that is a different problem and hiding it here would bury it.
    def set_dossiers(self, document_id: str, dossiers: list[str]) -> bool: ...
    def set_dossiers(self, document_id, dossiers) -> bool:
        if document_id not in self._docs:
            return False
        self._dossiers[document_id] = set(dossiers or ())
        return True

    def has_object_key(self, object_key: str) -> bool:
        return any(key == object_key for _t, key, _v in self._docs.values())

    def _in_scope(self, doc_id, only) -> bool:
        return only is None or bool(self._dossiers.get(doc_id, set()) & set(only))

    def _lexical(self, query: str, only=None) -> list[tuple[str, float]]:
        q = set(_terms(query))
        scored = []
        for doc_id, (text, _key, _vec) in self._docs.items():
            if not self._in_scope(doc_id, only):
                continue
            score = float(sum(1 for t in _terms(text) if t in q))
            if score > 0:
                scored.append((doc_id, score))
        scored.sort(key=lambda p: p[1], reverse=True)
        return scored

    def search(self, query: str, size: int = 10, only=None) -> list[Hit]:
        return [
            Hit(doc_id, score, self._docs[doc_id][1])
            for doc_id, score in self._lexical(query, only)[:size]
        ]

    def hybrid_search(self, query, query_vector, recall: int = 50,
                      only=None) -> list[Hit]:
        lexical_ids = [doc_id for doc_id, _ in self._lexical(query, only)]
        knn = sorted(
            ((doc_id, cosine(query_vector, vec))
             for doc_id, (_t, _k, vec) in self._docs.items()
             if vec and self._in_scope(doc_id, only)),
            key=lambda p: p[1], reverse=True,
        )
        knn_ids = [doc_id for doc_id, _ in knn]
        fused = fuse_ranked_ids([lexical_ids, knn_ids])[:recall]
        return [
            Hit(d, 0.0, self._docs[d][1], self._docs[d][2], self._docs[d][0])
            for d in fused
        ]
