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
