"""POST /ingest is registered only when the write-path deps are wired — offline.

The route drives the full straat (ingest -> anonymize -> store -> index); its
behaviour is covered by the pipeline/driver tests. Here we only assert wiring:
the endpoint appears when session_factory + store + search_index + embedder are
present, and is absent otherwise. Sentinels avoid touching any backend.
"""
from __future__ import annotations

import io

from fastapi.testclient import TestClient

from wordsworth.api import create_app


def _routes(app) -> set[tuple[str, str]]:
    return {
        (r.path, method)
        for r in app.routes
        for method in getattr(r, "methods", set()) or set()
    }


def test_ingest_registered_when_store_and_deps_present():
    app = create_app(
        session_factory=object(),
        search_index=object(),
        embedder=object(),
        store=object(),
        anonymizer=object(),   # avoid constructing the real driver
        rate_limiters={},
    )
    assert ("/ingest", "POST") in _routes(app)


def test_ingest_absent_without_store():
    app = create_app(
        session_factory=object(),
        search_index=object(),
        embedder=object(),
        rate_limiters={},
    )
    assert ("/ingest", "POST") not in _routes(app)


def test_document_meta_endpoint_registered_with_db():
    app = create_app(session_factory=object(), rate_limiters={})
    assert ("/documents/{document_id}", "GET") in _routes(app)


# --- provenance (ingest-records-source): rejected before any backend is touched -

def _wired_app():
    return create_app(
        session_factory=object(),
        search_index=object(),
        embedder=object(),
        store=object(),
        anonymizer=object(),   # avoid constructing the real driver
        rate_limiters={},
    )


def _upload():
    return {"files": ("x.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")}


def test_malformed_source_url_rejected_with_400_before_any_backend_is_touched():
    # Sentinel backends (plain object()) would blow up on first real use; a
    # 400 here proves validation ran before any of them was touched.
    client = TestClient(_wired_app())
    resp = client.post("/ingest", files=_upload(),
                       params={"dossier": "zaak-1", "source_url": "ftp://x/y"})
    assert resp.status_code == 400
    assert "https" in resp.json()["detail"]


def test_malformed_fetched_at_rejected_with_400_before_any_backend_is_touched():
    client = TestClient(_wired_app())
    resp = client.post("/ingest", files=_upload(),
                       params={"dossier": "zaak-1", "fetched_at": "not-a-date"})
    assert resp.status_code == 400
    assert "ISO-8601" in resp.json()["detail"]
