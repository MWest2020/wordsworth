"""Minimal FastAPI skeleton (fundament phase). Health + derived document state.

Kept thin on purpose: this change is the pipeline spine, not the API surface."""
from __future__ import annotations

from uuid import UUID

from fastapi import FastAPI, File, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session, sessionmaker

from .anonymizer import Anonymizer
from .config import settings as default_settings
from .embedder import Embedder
from .generator import Generator
from .object_store import ObjectStore
from .pipeline import current_state, ingest, process
from .rate_limit import (
    EXEMPT_PATHS,
    RateLimitMiddleware,
    TokenBucket,
    limiters_from_settings,
)
from .recovery import recover
from .search_index import SearchIndex
from .states import State


def create_app(
    session_factory: sessionmaker[Session] | None = None,
    search_index: SearchIndex | None = None,
    embedder: Embedder | None = None,
    generator: Generator | None = None,
    store: ObjectStore | None = None,
    anonymizer: Anonymizer | None = None,
    rate_limiters: dict[str, TokenBucket] | None = None,
) -> FastAPI:
    app = FastAPI(title="wordsworth")

    # Per-client rate limiting on the read endpoints; /health & /metrics exempt.
    # Built from settings by default; tests may inject their own limiters.
    limiters = (
        rate_limiters
        if rate_limiters is not None
        else limiters_from_settings(default_settings)
    )
    if limiters:
        app.add_middleware(
            RateLimitMiddleware, limiters=limiters, exempt=EXEMPT_PATHS
        )

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

            if generator is not None:

                @app.get("/ask")
                def ask(q: str, k: int = 5) -> dict:
                    from .rag import ask as run_ask

                    answer = run_ask(q, search_index, embedder, generator, k=k)
                    return {"query": q, "answer": answer.text,
                            "citations": answer.citations}

    # Write path: push a document through the full straat over HTTP. Needs the
    # object store + anonymizer in addition to the DB/index/embedder. Defaults to
    # the OpenAnonymiser (GLiNER) driver — the sovereign anonymize step.
    if (session_factory is not None and store is not None
            and search_index is not None and embedder is not None):
        if anonymizer is None:
            from .openanonymiser_driver import OpenAnonymiserAnonymizer

            anonymizer = OpenAnonymiserAnonymizer()

        @app.post("/ingest")
        async def ingest_document(file: UploadFile = File(...)) -> dict:
            data = await file.read()
            if not data:
                raise HTTPException(status_code=400, detail="empty upload")
            try:
                with session_factory() as session:
                    doc = ingest(session, store, data)
                    session.commit()
                    state = process(session, doc.id, store, anonymizer=anonymizer,
                                    search_index=search_index, embedder=embedder)
                    session.commit()
                    if state == State.UNPROCESSABLE_OCR:
                        # Scanned page: OCR to a text layer, then resume the straat.
                        recover(session, doc.id, store)
                        session.commit()
                        state = process(session, doc.id, store,
                                        anonymizer=anonymizer,
                                        search_index=search_index,
                                        embedder=embedder)
                        session.commit()
                    doc_id = doc.id
            except Exception as exc:  # fail-hard; carry no document text out
                raise HTTPException(
                    status_code=502, detail=f"ingest failed: {type(exc).__name__}"
                ) from exc
            return {"document_id": str(doc_id), "filename": file.filename,
                    "state": state.value}

    return app


def _hit(h) -> dict:
    # Omit the raw vector from API responses; expose the useful fields only.
    return {"document_id": h.document_id, "score": h.score, "object_key": h.object_key}
