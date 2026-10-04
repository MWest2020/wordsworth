# SPDX-License-Identifier: MIT
"""Passages in production (long-documents-rank-fairly, candidate 2a, #190).

A long document's one vector averages over everything in it; its best passage
does not. These pin the production path: indexing writes passages from the text
it indexes, the backfill fills the rest without touching anything else, and the
kNN half can rank a document by its best passage behind a setting.
"""
import pytest

from wordsworth.backfill_passages import run as backfill
from wordsworth.embedder import DeterministicEmbedder, EmbeddingUnavailable
from wordsworth.hybrid import hybrid_search
from wordsworth.opensearch_index import _mapping, _scoped_knn
from wordsworth.passages import embed_passages, split
from wordsworth.pipeline import ingest, process, reanonymize
from wordsworth.search_index import InMemoryIndex

LONG = " ".join(f"woord{i}" for i in range(700))


def _corpus():
    """'long' has a far whole-document vector but one passage right on the
    query; 'short' has a whole-document vector fairly close to it."""
    index = InMemoryIndex()
    index.index("long", "lang stuk", "k-long", vector=[0.2, 1.0],
                passages=[[0.0, 1.0], [0.0, 1.0], [1.0, 0.05]])
    index.index("short", "kort stuk", "k-short", vector=[0.7, 0.7],
                passages=[[0.7, 0.7]])
    return index


class _Q:
    dim = 2

    def embed(self, texts):
        return [[1.0, 0.0] for _ in texts]


def _order(index, **kw):
    return [h.document_id for h in hybrid_search(index, _Q(), "niets", size=2,
                                                 final="rrf", **kw)]


def test_the_knn_half_can_rank_a_document_by_its_best_passage():
    assert _order(_corpus(), knn="document") == ["short", "long"]
    assert _order(_corpus(), knn="passage") == ["long", "short"]


def test_the_setting_switches_it_and_refuses_nonsense(monkeypatch):
    monkeypatch.setenv("WORDSWORTH_HYBRID_KNN", "passage")
    assert _order(_corpus()) == ["long", "short"]
    monkeypatch.setenv("WORDSWORTH_HYBRID_KNN", "passages")
    with pytest.raises(ValueError):
        _order(_corpus())


def test_a_document_has_one_vector_per_passage():
    vecs = embed_passages(DeterministicEmbedder(16), LONG)
    assert len(vecs) == len(split(LONG)) > 1
    assert embed_passages(DeterministicEmbedder(16), "   ") == []


def test_indexing_writes_the_passages_of_the_indexed_text(
        session, born_digital_pii_pdf, mem_store, fake_embedder):
    index = InMemoryIndex()
    doc = ingest(session, mem_store, born_digital_pii_pdf)
    session.commit()
    process(session, doc.id, mem_store, search_index=index, embedder=fake_embedder)
    text = index._docs[str(doc.id)][0]
    assert len(index._passages[str(doc.id)]) == len(split(text)) >= 1


def test_reanonymizing_rewrites_the_passages_too(
        session, born_digital_pii_pdf, mem_store, fake_embedder):
    index = InMemoryIndex()
    doc = ingest(session, mem_store, born_digital_pii_pdf)
    session.commit()
    process(session, doc.id, mem_store, search_index=index, embedder=fake_embedder)
    session.commit()
    index._passages.pop(str(doc.id))          # as if indexed before passages existed
    reanonymize(session, doc.id, mem_store, search_index=index, embedder=fake_embedder)
    assert index._passages[str(doc.id)]


def test_set_passages_touches_nothing_else():
    index = _corpus()
    assert index.set_passages("short", [[0.1, 0.9]])
    assert index._docs["short"] == ("kort stuk", "k-short", [0.7, 0.7])
    assert index.set_passages("absent", [[1.0, 0.0]]) is False


def test_the_backfill_fills_what_is_missing_and_ends():
    index = InMemoryIndex()
    index.index("a", LONG, "ka", vector=[1.0])
    index.index("b", "kort", "kb", vector=[1.0])
    index.index("c", "", "kc", vector=[1.0])            # no text, no passages
    index.index("d", "al klaar", "kd", vector=[1.0], passages=[[9.0]])
    stats = backfill(index, DeterministicEmbedder(8), workers=2, batch=2, log=lambda m: None)
    assert stats["documents"] == 2 and stats["empty"] == 1 and stats["failed"] == 0
    assert len(index._passages["a"]) == len(split(LONG))
    assert index._passages["d"] == [[9.0]]              # left alone
    assert index._docs["a"][2] == [1.0]                 # vector untouched


def test_a_failing_document_is_set_aside_not_retried_forever(monkeypatch):
    monkeypatch.setenv("WORDSWORTH_RETRY_BASE_DELAY", "0")

    class _Broken(DeterministicEmbedder):
        def embed(self, texts):
            if "kapot" in texts[0]:
                raise EmbeddingUnavailable("gone")
            return super().embed(texts)

    index = InMemoryIndex()
    index.index("ok", "werkt prima", "k1", vector=[1.0])
    index.index("bad", "kapot stuk", "k2", vector=[1.0])
    stats = backfill(index, _Broken(8), workers=1, batch=10, log=lambda m: None)
    assert stats["documents"] == 1 and stats["failed"] == 1
    assert "bad" not in index._passages


def test_opensearch_maps_passages_nested_and_filters_inside_the_knn():
    props = _mapping(1024)["mappings"]["properties"]
    assert props["passages"]["type"] == "nested"
    assert props["passages"]["properties"]["vector"]["dimension"] == 1024
    q = _scoped_knn([1.0, 0.0], 50, ["d1"], knn="passage")
    inner = q["nested"]["query"]["knn"]["passages.vector"]
    assert q["nested"]["score_mode"] == "max" and inner["k"] == 50 and "filter" in inner
    assert "knn" in _scoped_knn([1.0, 0.0], 50, None)    # the document form is unchanged
