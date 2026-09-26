"""Hybrid search orchestration: embed the query, take an RRF recall set from the
index (BM25 + kNN), then let zeef's cosine be the final selector.

RRF gives recall (candidate set); `zeef.similarity.cosine` gives the order —
the proven '--no-llm + cosine' selection path. No LLM, no clustering."""
from __future__ import annotations

from zeef.similarity import cosine

from .config import settings
from .embedder import Embedder
from .retry import retry_transient
from .search_index import Hit, SearchIndex


def hybrid_search(
    index: SearchIndex,
    embedder: Embedder,
    query: str,
    size: int = 10,
    recall: int = 50,
    only: list[str] | None = None,
    topic: str | None = None,
) -> list[Hit]:
    # The same bounded retry as ingest (hoge-beschikbaarheid 3.2.4): with two
    # Ollama instances, a query can reach one in the second it goes away --
    # measured 2026-09-26, 1 of 334 queries got "connection refused" while its
    # endpoint was being removed. Only transport failures retry; a bad
    # embedding does not, and after the budget it is still an error.
    query_vector = retry_transient(lambda: embedder.embed([query])[0],
                                   settings.retry_attempts, settings.retry_base_delay,
                                   what="query_embed")
    candidates = index.hybrid_search(query, query_vector, recall=recall, only=only,
                                     topic=topic)
    for hit in candidates:
        hit.score = round(cosine(query_vector, hit.vector), 6) if hit.vector else 0.0
    candidates.sort(key=lambda h: h.score, reverse=True)
    return candidates[:size]
