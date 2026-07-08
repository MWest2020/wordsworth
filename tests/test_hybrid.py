import pytest

from wordsworth.embedder import DeterministicEmbedder
from wordsworth.hybrid import hybrid_search
from wordsworth.search_index import InMemoryIndex


def _add(index, embedder, doc_id, text):
    index.index(doc_id, text, doc_id, vector=embedder.embed([text])[0])


def test_hybrid_ranks_relevant_first():
    emb = DeterministicEmbedder(dim=64)
    idx = InMemoryIndex()
    _add(idx, emb, "relevant", "de gemeente Haarlem besluit over parkeervergunningen")
    _add(idx, emb, "off", "notulen over hondenbeleid en groenvoorziening")
    hits = hybrid_search(idx, emb, "parkeervergunningen Haarlem")
    assert hits[0].document_id == "relevant"
    assert hits[0].score > 0


def test_final_score_is_zeef_cosine():
    emb = DeterministicEmbedder(dim=64)
    idx = InMemoryIndex()
    _add(idx, emb, "d", "parkeren parkeren parkeren")
    hits = hybrid_search(idx, emb, "parkeren parkeren parkeren")
    assert hits[0].document_id == "d"
    # identical text -> identical vector -> cosine 1.0 (the selector)
    assert hits[0].score == pytest.approx(1.0, abs=1e-6)
