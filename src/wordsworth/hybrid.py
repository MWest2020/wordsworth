"""Hybrid search orchestration: embed the query, take an RRF recall set from the
index (BM25 + kNN), then let zeef's cosine be the final selector.

RRF gives recall (candidate set); `zeef.similarity.cosine` gives the order —
the proven '--no-llm + cosine' selection path. No LLM, no clustering."""
from __future__ import annotations

from zeef.similarity import cosine

from .embedder import Embedder
from .search_index import Hit, SearchIndex


def hybrid_search(
    index: SearchIndex,
    embedder: Embedder,
    query: str,
    size: int = 10,
    recall: int = 50,
) -> list[Hit]:
    query_vector = embedder.embed([query])[0]
    candidates = index.hybrid_search(query, query_vector, recall=recall)
    for hit in candidates:
        hit.score = round(cosine(query_vector, hit.vector), 6) if hit.vector else 0.0
    candidates.sort(key=lambda h: h.score, reverse=True)
    return candidates[:size]
