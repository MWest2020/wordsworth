"""POST /ingest is registered only when the write-path deps are wired — offline.

The route drives the full straat (ingest -> anonymize -> store -> index); its
behaviour is covered by the pipeline/driver tests. Here we only assert wiring:
the endpoint appears when session_factory + store + search_index + embedder are
present, and is absent otherwise. Sentinels avoid touching any backend.
"""
from __future__ import annotations

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
