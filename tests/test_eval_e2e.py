"""End-to-end: evaluate real in-memory rankers over a small synthetic Dutch
collection. No database, OpenSearch, or Ollama — the harness needs none."""
import pytest

from wordsworth.embedder import DeterministicEmbedder
from wordsworth.eval.harness import evaluate
from wordsworth.hybrid import hybrid_search
from wordsworth.search_index import InMemoryIndex

DOCS = {
    "doc_park": "de gemeente Haarlem verleent parkeervergunningen aan bewoners",
    "doc_park2": "aanvraag parkeervergunningen door bewoners van Haarlem centrum",
    "doc_hond": "notulen over hondenbeleid en groenvoorziening in het park",
    "doc_bouw": "de raad besluit over een nieuwe bouwvergunning in het centrum",
}
QUERIES = {
    "q_park": "parkeervergunningen Haarlem bewoners",
    "q_bouw": "bouwvergunning centrum raad",
}
QRELS = {
    "q_park": {"doc_park": 1, "doc_park2": 1},
    "q_bouw": {"doc_bouw": 1},
}


def _build():
    emb = DeterministicEmbedder(dim=64)
    idx = InMemoryIndex()
    for doc_id, text in DOCS.items():
        idx.index(doc_id, text, doc_id, vector=emb.embed([text])[0])
    return idx, emb


def test_bm25_stand_in_ranker_scores_well():
    idx, _ = _build()

    def search(query: str) -> list[str]:
        return [hit.document_id for hit in idx.search(query, size=10)]

    report = evaluate(search, QUERIES, QRELS)
    # Every relevant doc is retrieved for both queries.
    assert report["aggregate"]["recall@10"] == pytest.approx(1.0)
    assert report["aggregate"]["r_precision"] == pytest.approx(1.0)
    assert report["aggregate"]["map"] == pytest.approx(1.0)


def test_hybrid_ranker_plugs_into_the_same_harness():
    idx, emb = _build()

    def search(query: str) -> list[str]:
        return [hit.document_id for hit in hybrid_search(idx, emb, query, size=10)]

    report = evaluate(search, QUERIES, QRELS)
    assert 0.0 <= report["aggregate"]["ndcg@10"] <= 1.0
    assert report["aggregate"]["recall@10"] == pytest.approx(1.0)


def test_metrics_are_reproducible():
    idx, _ = _build()

    def search(query: str) -> list[str]:
        return [hit.document_id for hit in idx.search(query, size=10)]

    first = evaluate(search, QUERIES, QRELS)
    second = evaluate(search, QUERIES, QRELS)
    assert first == second


def test_a_degraded_ranker_scores_lower():
    idx, _ = _build()

    def good(query: str) -> list[str]:
        return [hit.document_id for hit in idx.search(query, size=10)]

    def degraded(query: str) -> list[str]:
        # Push non-relevant noise ahead of the real hits.
        return ["noise_a", "noise_b"] + good(query)

    good_map = evaluate(good, QUERIES, QRELS)["aggregate"]["map"]
    degraded_map = evaluate(degraded, QUERIES, QRELS)["aggregate"]["map"]
    assert degraded_map < good_map
