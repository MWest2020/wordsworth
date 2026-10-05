"""Hybrid search orchestration: embed the query, take an RRF recall set from the
index (BM25 + kNN), and order it.

The order is the fused RRF rank since 2026-10-05 (change
long-documents-rank-fairly). The earlier final selector, `zeef.similarity.cosine`
against one embedding per whole document, found not one long document by its
own title on the Woo collection; it stays as a rollback (`final="cosine"`).
No LLM, no clustering."""
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
    final: str | None = None,
    knn: str | None = None,
) -> list[Hit]:
    """Hybrid search: RRF recall over BM25 + kNN, then the final order.

    ``final`` -- "cosine" re-sorts the recall set by cosine between the query
    and each document's one embedding; "rrf" keeps the fused rank the recall
    stage computed. ``None`` reads ``WORDSWORTH_HYBRID_FINAL_RANK`` (default
    rrf). Either way ``score`` is the cosine similarity; under "rrf" it no
    longer decides the order (change long-documents-rank-fairly: cosine over
    whole-document embeddings ranks long documents last).
    """
    final = final or settings.hybrid_final_rank
    if final not in ("cosine", "rrf"):
        raise ValueError(f"final rank must be cosine or rrf, not {final!r}")
    # ``knn`` -- "document" or "passage" (WORDSWORTH_HYBRID_KNN): what the kNN
    # half of the recall compares the query with.
    knn = knn or settings.hybrid_knn
    if knn not in ("document", "passage"):
        raise ValueError(f"knn must be document or passage, not {knn!r}")
    # The same bounded retry as ingest (hoge-beschikbaarheid 3.2.4): with two
    # Ollama instances, a query can reach one in the second it goes away --
    # measured 2026-09-26, 1 of 334 queries got "connection refused" while its
    # endpoint was being removed. Only transport failures retry; a bad
    # embedding does not, and after the budget it is still an error.
    query_vector = retry_transient(lambda: embedder.embed([query])[0],
                                   settings.retry_attempts, settings.retry_base_delay,
                                   what="query_embed")
    candidates = index.hybrid_search(query, query_vector, recall=recall, only=only,
                                     topic=topic, knn=knn)
    for hit in candidates:
        hit.score = round(cosine(query_vector, hit.vector), 6) if hit.vector else 0.0
    if final == "cosine":
        candidates.sort(key=lambda h: h.score, reverse=True)
    return candidates[:size]
