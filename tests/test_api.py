from fastapi.testclient import TestClient

from wordsworth.api import create_app
from wordsworth.search_index import InMemoryIndex


def test_health_needs_no_database():
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_search_endpoint_returns_ranked_hits():
    index = InMemoryIndex()
    index.index("d1", "parkeren in Haarlem", "k1")
    index.index("d2", "iets over honden", "k2")
    client = TestClient(create_app(search_index=index))
    response = client.get("/search", params={"q": "parkeren"})
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "parkeren"
    assert body["hits"][0]["document_id"] == "d1"


def test_hybrid_endpoint_returns_ranked_hits():
    from wordsworth.embedder import DeterministicEmbedder

    emb = DeterministicEmbedder(dim=64)
    index = InMemoryIndex()
    for doc_id, text in [("d1", "parkeren in Haarlem"), ("d2", "iets over honden")]:
        index.index(doc_id, text, doc_id, vector=emb.embed([text])[0])
    client = TestClient(create_app(search_index=index, embedder=emb))
    response = client.get("/hybrid", params={"q": "parkeren"})
    assert response.status_code == 200
    body = response.json()
    assert body["hits"][0]["document_id"] == "d1"
    assert "vector" not in body["hits"][0]  # raw vectors are not exposed


def test_ask_endpoint_returns_answer_and_verified_citations():
    from wordsworth.embedder import DeterministicEmbedder
    from wordsworth.generator import DeterministicGenerator

    emb = DeterministicEmbedder(dim=64)
    index = InMemoryIndex()
    for doc_id, text in [("d1", "parkeren in Haarlem"), ("d2", "iets over honden")]:
        index.index(doc_id, text, doc_id, vector=emb.embed([text])[0])
    # Generator invents a citation; the endpoint must only return verified ids.
    gen = DeterministicGenerator(extra_citations=["ghost"])
    client = TestClient(create_app(search_index=index, embedder=emb, generator=gen))
    response = client.get("/ask", params={"q": "parkeren", "k": 1})
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "parkeren"
    assert body["answer"]
    assert body["citations"] == ["d1"]
    assert "ghost" not in body["citations"]
