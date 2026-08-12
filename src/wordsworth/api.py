"""FastAPI surface for Wordsworth.

Read path: document state, metrics, search, hybrid search, ask (RAG). Write path:
``POST /ingest`` pushes one or more PDFs through the full straat. Routes are
registered per injected dependency, so the same factory serves a health-only app
or the full surface. Interactive docs at ``/docs`` (Swagger) and ``/redoc``.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import FastAPI, File, HTTPException, Response, UploadFile
from pydantic import BaseModel
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

API_DESCRIPTION = (
    "Sovereign pipeline that turns government PDFs into a searchable, "
    "privacy-safe corpus. Documents are de-identified (deterministic BSN/IBAN/"
    "email + OpenAnonymiser GLiNER for entity PII) before they are indexed; no "
    "clear PII reaches the index."
)


class IngestResult(BaseModel):
    """Outcome for a single uploaded file."""

    filename: str | None = None
    document_id: str | None = None
    state: str
    error: str | None = None


class IngestResponse(BaseModel):
    """Per-file results for an ingest batch."""

    total: int
    indexed: int
    results: list[IngestResult]


def create_app(
    session_factory: sessionmaker[Session] | None = None,
    search_index: SearchIndex | None = None,
    embedder: Embedder | None = None,
    generator: Generator | None = None,
    store: ObjectStore | None = None,
    anonymizer: Anonymizer | None = None,
    rate_limiters: dict[str, TokenBucket] | None = None,
) -> FastAPI:
    app = FastAPI(
        title="wordsworth",
        version="0.1.0",
        description=API_DESCRIPTION,
    )

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

    @app.get("/health", summary="Liveness probe", tags=["ops"])
    def health() -> dict[str, str]:
        """Always-on health check (no backend access)."""
        return {"status": "ok"}

    if session_factory is not None:

        @app.get("/documents/{document_id}/state",
                 summary="Current pipeline state of a document", tags=["read"])
        def document_state(document_id: UUID) -> dict[str, str]:
            """Derived state (registered → extractable/unprocessable_ocr →
            extracted → anonymized → indexed) from the audit chain."""
            with session_factory() as session:
                state = current_state(session, document_id)
            if state is None:
                raise HTTPException(status_code=404, detail="unknown document")
            return {"document_id": str(document_id), "state": state.value}

        @app.get("/metrics", summary="Prometheus metrics", tags=["ops"])
        def metrics() -> Response:
            """Pipeline metrics in Prometheus text format."""
            from .metrics import CONTENT_TYPE, render_metrics

            with session_factory() as session:
                body = render_metrics(session)
            return Response(content=body, media_type=CONTENT_TYPE)

    if search_index is not None:

        @app.get("/search", summary="Lexical (BM25) search", tags=["read"])
        def search(q: str, size: int = 10) -> dict:
            """Full-text search over the anonymized corpus."""
            hits = search_index.search(q, size=size)
            return {"query": q, "hits": [_hit(h) for h in hits]}

        if embedder is not None:

            @app.get("/hybrid", summary="Hybrid (BM25 + kNN) search",
                     tags=["read"])
            def hybrid(q: str, size: int = 10) -> dict:
                """RRF recall over BM25 + vector kNN, ranked by cosine."""
                from .hybrid import hybrid_search

                hits = hybrid_search(search_index, embedder, q, size=size)
                return {"query": q, "hits": [_hit(h) for h in hits]}

            if generator is not None:

                @app.get("/ask", summary="RAG question answering", tags=["read"])
                def ask(q: str, k: int = 5) -> dict:
                    """Retrieve top-k passages and answer with the local LLM
                    (no cloud in the critical path)."""
                    from .rag import ask as run_ask

                    answer = run_ask(q, search_index, embedder, generator, k=k)
                    return {"query": q, "answer": answer.text,
                            "citations": answer.citations}

    # Write path: push documents through the full straat over HTTP. Needs the
    # object store + anonymizer in addition to the DB/index/embedder. Defaults to
    # the OpenAnonymiser (GLiNER) driver — the sovereign anonymize step.
    if (session_factory is not None and store is not None
            and search_index is not None and embedder is not None):
        if anonymizer is None:
            from .openanonymiser_driver import OpenAnonymiserAnonymizer

            anonymizer = OpenAnonymiserAnonymizer()

        def _ingest_one(data: bytes) -> str:
            """Drive one document to its terminal state; return the state value.
            The un-redacted bytes never leave this frame and no exception it
            raises carries document text (fail-hard, no silent pass-through)."""
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
                    state = process(session, doc.id, store, anonymizer=anonymizer,
                                    search_index=search_index, embedder=embedder)
                    session.commit()
                return str(doc.id), state.value

        @app.post("/ingest", response_model=IngestResponse, tags=["write"],
                  summary="Ingest one or more PDFs through the full straat")
        async def ingest_documents(
            files: list[UploadFile] = File(..., description="One or more PDF files"),
        ) -> IngestResponse:
            """Upload one or more PDFs. Each is driven through
            ingest → OCR recovery (if scanned) → anonymize → store → index and
            reported individually. A failing file does not abort the batch and
            never leaks document text (only its error class is returned)."""
            results: list[IngestResult] = []
            for f in files:
                data = await f.read()
                if not data:
                    results.append(IngestResult(
                        filename=f.filename, state="error", error="empty upload"))
                    continue
                try:
                    doc_id, state = _ingest_one(data)
                    results.append(IngestResult(
                        filename=f.filename, document_id=doc_id, state=state))
                except Exception as exc:  # fail-hard; carry no document text out
                    results.append(IngestResult(
                        filename=f.filename, state="error",
                        error=type(exc).__name__))
            indexed = sum(1 for r in results if r.state == "indexed")
            return IngestResponse(total=len(results), indexed=indexed,
                                  results=results)

    return app


def _hit(h) -> dict:
    # Omit the raw vector from API responses; expose the useful fields only.
    return {"document_id": h.document_id, "score": h.score, "object_key": h.object_key}
