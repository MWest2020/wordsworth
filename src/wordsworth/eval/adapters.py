"""Ranker adapters: expose BM25 and hybrid search as the harness's
`search(query) -> ranked document ids` callable.

Both adapters return the documents' **external id** (`object_key`), not the
internal uuid, so the ranked ids share one namespace with the qrels' document
ids (precondition: the corpus is ingested with `object_key` = qrels doc id).
A hit without an `object_key` is a hard error — no silent fallbacks."""
from __future__ import annotations

from collections.abc import Callable

from ..embedder import Embedder
from ..hybrid import hybrid_search
from ..search_index import Hit, SearchIndex

Ranker = Callable[[str], list[str]]


def _external_ids(hits: list[Hit]) -> list[str]:
    ids: list[str] = []
    for hit in hits:
        if not hit.object_key:
            raise ValueError(
                f"hit {hit.document_id!r} has no object_key; evaluation needs "
                "the external id to match the qrels namespace"
            )
        ids.append(hit.object_key)
    return ids


def bm25_adapter(index: SearchIndex, k: int = 10) -> Ranker:
    """BM25 configuration: `index.search`, ranked external ids."""

    def search(query: str) -> list[str]:
        return _external_ids(index.search(query, size=k))

    return search


def hybrid_adapter(index: SearchIndex, embedder: Embedder, k: int = 10) -> Ranker:
    """Hybrid configuration: RRF recall + zeef cosine, ranked external ids."""

    def search(query: str) -> list[str]:
        return _external_ids(hybrid_search(index, embedder, query, size=k))

    return search
