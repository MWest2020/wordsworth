"""RAG /ask endpoint end-to-end against a real OpenSearch retrieval backend.

test_api.py already covers /ask, but wired to the InMemoryIndex double — a
component test. This drives the same endpoint through the *real* OpenSearch hybrid
path (BM25 + kNN + zeef cosine). The LLM is stubbed with DeterministicGenerator:
the integration surface under test is the retrieval backend plus the endpoint
wiring and the grounding guard, not the model. Skipped when no OpenSearch is
reachable, matching test_hybrid_opensearch.py / test_opensearch_index.py."""
import pytest
from fastapi.testclient import TestClient

from wordsworth.api import create_app
from wordsworth.config import settings
from wordsworth.embedder import DeterministicEmbedder
from wordsworth.generator import DeterministicGenerator
from wordsworth.opensearch_index import OpenSearchIndex


@pytest.fixture
def os_index():
    pytest.importorskip("opensearchpy")
    from opensearchpy import OpenSearch

    client = OpenSearch(hosts=[settings.opensearch_url])
    try:
        client.info()
    except Exception:
        pytest.skip("OpenSearch not reachable")
    name = "wordsworth_ask_test"
    client.indices.delete(index=name, ignore=[404])
    index = OpenSearchIndex(client, name, dim=64)
    index.ensure_ready()
    yield index
    client.indices.delete(index=name, ignore=[404])


def _populate(index, emb):
    for doc_id, text in [
        ("relevant", "gemeente Haarlem besluit over parkeervergunningen"),
        ("off", "notulen over hondenbeleid en groenvoorziening"),
    ]:
        index.index(doc_id, text, doc_id, vector=emb.embed([text])[0])


def test_ask_endpoint_over_opensearch_returns_grounded_answer(os_index):
    emb = DeterministicEmbedder(dim=64)
    _populate(os_index, emb)
    client = TestClient(
        create_app(search_index=os_index, embedder=emb,
                   generator=DeterministicGenerator())
    )

    response = client.get("/ask", params={"q": "parkeervergunningen Haarlem", "k": 1})

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "parkeervergunningen Haarlem"
    assert body["answer"]
    # The top hit from real OpenSearch retrieval is the relevant doc, and it
    # survives the grounding guard as the returned citation.
    assert body["citations"] == ["relevant"]


def test_ask_endpoint_over_opensearch_drops_invented_citation(os_index):
    emb = DeterministicEmbedder(dim=64)
    _populate(os_index, emb)
    # Generator cites the retrieved doc plus an id that was never retrieved; the
    # deterministic guard must drop the invented one even over the real backend.
    client = TestClient(
        create_app(search_index=os_index, embedder=emb,
                   generator=DeterministicGenerator(extra_citations=["ghost"]))
    )

    response = client.get("/ask", params={"q": "parkeervergunningen Haarlem", "k": 1})

    assert response.status_code == 200
    body = response.json()
    assert "ghost" not in body["citations"]
    assert body["citations"] == ["relevant"]
