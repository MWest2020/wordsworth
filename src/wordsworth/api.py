"""Minimal FastAPI skeleton (fundament phase). Health + derived document state.

Kept thin on purpose: this change is the pipeline spine, not the API surface."""
from __future__ import annotations

from uuid import UUID

from fastapi import FastAPI, HTTPException, Response
from sqlalchemy.orm import Session, sessionmaker

from .embedder import Embedder
from .pipeline import current_state
from .search_index import SearchIndex


def create_app(
    session_factory: sessionmaker[Session] | None = None,
    search_index: SearchIndex | None = None,
    embedder: Embedder | None = None,
) -> FastAPI:
    app = FastAPI(title="wordsworth")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    if session_factory is not None:

        @app.get("/documents/{document_id}/state")
        def document_state(document_id: UUID) -> dict[str, str]:
            with session_factory() as session:
                state = current_state(session, document_id)
            if state is None:
                raise HTTPException(status_code=404, detail="unknown document")
            return {"document_id": str(document_id), "state": state.value}

        @app.get("/metrics")
        def metrics() -> Response:
            from .metrics import CONTENT_TYPE, render_metrics

            with session_factory() as session:
                body = render_metrics(session)
            return Response(content=body, media_type=CONTENT_TYPE)

    if search_index is not None:

        @app.get("/search")
        def search(q: str, size: int = 10) -> dict:
            hits = search_index.search(q, size=size)
            return {"query": q, "hits": [_hit(h) for h in hits]}

        if embedder is not None:

            @app.get("/hybrid")
            def hybrid(q: str, size: int = 10) -> dict:
                from .hybrid import hybrid_search

                hits = hybrid_search(search_index, embedder, q, size=size)
                return {"query": q, "hits": [_hit(h) for h in hits]}

    return app


def _hit(h) -> dict:
    # Omit the raw vector from API responses; expose the useful fields only.
    return {"document_id": h.document_id, "score": h.score, "object_key": h.object_key}
