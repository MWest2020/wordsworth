from fastapi.testclient import TestClient

from wordsworth.api import create_app


def test_health_needs_no_database():
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
