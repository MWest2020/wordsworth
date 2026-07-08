"""Hybrid (BM25 + kNN RRF + zeef cosine) against a real OpenSearch. Skip if none."""
import pytest

from wordsworth.config import settings
from wordsworth.embedder import DeterministicEmbedder
from wordsworth.hybrid import hybrid_search
from wordsworth.opensearch_index import OpenSearchIndex


@pytest.fixture
def os_hybrid():
    pytest.importorskip("opensearchpy")
    from opensearchpy import OpenSearch

    client = OpenSearch(hosts=[settings.opensearch_url])
    try:
        client.info()
    except Exception:
        pytest.skip("OpenSearch not reachable")
    name = "wordsworth_hybrid_test"
    client.indices.delete(index=name, ignore=[404])
    index = OpenSearchIndex(client, name, dim=64)
    index.ensure_ready()
    yield index
    client.indices.delete(index=name, ignore=[404])


def test_hybrid_over_opensearch_ranks_relevant_first(os_hybrid):
    emb = DeterministicEmbedder(dim=64)

    def add(doc_id, text):
        os_hybrid.index(doc_id, text, doc_id, vector=emb.embed([text])[0])

    add("relevant", "gemeente Haarlem besluit over parkeervergunningen")
    add("off", "notulen over hondenbeleid en groenvoorziening")
    hits = hybrid_search(os_hybrid, emb, "parkeervergunningen Haarlem")
    assert hits[0].document_id == "relevant"
    assert hits[0].score > 0
