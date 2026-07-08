"""Minimal FastAPI skeleton (fundament phase). Health + derived document state.

Kept thin on purpose: this change is the pipeline spine, not the API surface."""
from __future__ import annotations

from uuid import UUID

from fastapi import FastAPI, HTTPException
from sqlalchemy.orm import Session, sessionmaker

from .pipeline import current_state
from .search_index import SearchIndex


def create_app(
    session_factory: sessionmaker[Session] | None = None,
    search_index: SearchIndex | None = None,
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

    if search_index is not None:

        @app.get("/search")
        def search(q: str, size: int = 10) -> dict:
            hits = search_index.search(q, size=size)
            return {"query": q, "hits": [vars(h) for h in hits]}

    return app
