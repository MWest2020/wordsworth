"""FastAPI surface for Wordsworth.

Read path: document state, metrics, search, hybrid search, ask (RAG). Write path:
``POST /ingest`` pushes one or more PDFs through the full straat. Routes are
registered per injected dependency, so the same factory serves a health-only app
or the full surface. Interactive docs at ``/docs`` (Swagger) and ``/redoc``.
"""
from __future__ import annotations

import csv
import hashlib
import io
import zipfile
from datetime import datetime, timezone
from typing import Callable
from uuid import UUID

from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .anonymizer import Anonymizer
from .auth import ApiKeyAuthMiddleware
from .config import settings as default_settings
from .embedder import Embedder
from .generator import Generator
from .grants import GrantStore
from .key_audit import KeyLifecycleAudit
from .keys import KeyProvider
from .models import AuditRecord, Document
from .object_store import ObjectStore
from .pipeline import current_state, get_anonymized_text, ingest, process
from .rate_limit import (
    EXEMPT_PATHS,
    RateLimitMiddleware,
    TokenBucket,
    limiters_from_settings,
)
from .recovery import recover
from .retry import is_transient
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
    duration_ms: float | None = None
    counts: dict[str, int] | None = None
    error: str | None = None


class IngestResponse(BaseModel):
    """Per-file results for an ingest batch."""

    total: int
    indexed: int
    results: list[IngestResult]


class RevealRequest(BaseModel):
    """A key-gated reveal request: which grant authorises it, and (optionally)
    which PII types to reveal. Omit ``types`` to reveal exactly what the grant
    allows."""

    grant_id: str
    types: list[str] | None = None


class RevealResponse(BaseModel):
    """The document text with the authorised PII types revealed; every other
    type stays pseudonymised. ``withheld_types`` are the requested types the
    grant did not authorise."""

    document_id: str
    revealed_text: str
    revealed_types: list[str]
    withheld_types: list[str]
    grant_id: str


class ReprocessRequest(BaseModel):
    """Backfill request: which documents to re-de-identify. Omit to reprocess
    every INDEXED document."""

    document_ids: list[str] | None = None


class ReprocessResponse(BaseModel):
    """Per-document outcome counts for a backfill run."""

    total: int
    reanonymized: int
    skipped: int
    retryable: int
    failed: int


class GrantIssueRequest(BaseModel):
    """Operator/admin request to issue a reveal grant. NB: this surface has no
    caller authentication yet — the API is tailnet-internal and the returned
    grant_id is a bearer capability; a real auth decision is pending."""

    recipient: str
    allowed_types: list[str]
    document_id: str | None = None      # None = any document
    expires_at: str | None = None       # ISO-8601, must be timezone-aware


class GrantResponse(BaseModel):
    """A grant's state — never any key material or clear PII."""

    grant_id: str
    recipient: str
    allowed_types: list[str]
    document_id: str | None
    status: str
    created_at: str
    revoked_at: str | None
    expires_at: str | None


def create_app(
    session_factory: sessionmaker[Session] | None = None,
    search_index: SearchIndex | None = None,
    embedder: Embedder | None = None,
    generator: Generator | None = None,
    store: ObjectStore | None = None,
    anonymizer: Anonymizer | None = None,
    key_provider: KeyProvider | None = None,
    grant_store: GrantStore | None = None,
    rate_limiters: dict[str, TokenBucket] | None = None,
    anonymizer_factory: Callable[[Session], Anonymizer] | None = None,
    key_provider_factory: Callable[[Session], KeyProvider] | None = None,
    grant_store_factory: Callable[[Session], GrantStore] | None = None,
    key_audit: KeyLifecycleAudit | None = None,
    api_keys: dict[str, str] | None = None,
) -> FastAPI:
    # Session-scoped backends (durable keys, Postgres mapping/grant stores) are
    # supplied as factories built per request; the singleton params stay for
    # tests and session-free doubles. A factory wins over its singleton.
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

    # Opt-in per-caller API-key auth. Mounted ONLY when keys are configured, so
    # an empty set leaves the API open (unchanged, non-breaking). Added last so
    # it runs first — an unauthenticated caller is rejected before rate-limiting.
    keys = api_keys if api_keys is not None else default_settings.api_keys
    if keys:
        app.add_middleware(
            ApiKeyAuthMiddleware, keys=keys, exempt=EXEMPT_PATHS
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

        @app.get("/documents/{document_id}",
                 summary="Document metadata (state, timing, PII counts, trail)",
                 tags=["read"])
        def document_meta(document_id: UUID) -> dict:
            """State, total + per-step processing duration, PII redaction counts,
            page/byte metrics and the audit-step trail — all derived from the
            append-only audit chain."""
            with session_factory() as session:
                meta = _document_meta(session, document_id)
            if meta is None:
                raise HTTPException(status_code=404, detail="unknown document")
            return meta

        @app.get("/export/anonymized.zip",
                 summary="Export de-identified document texts as a ZIP",
                 tags=["export"])
        def export_anonymized(document_ids: str | None = None) -> Response:
            """A ZIP of the stored de-identified texts (one ``{id}.txt`` per
            document), for all INDEXED documents or the given comma-separated
            subset. Only the index-bound anonymized text is written — never clear
            PII, never original bytes."""
            ids = None
            if document_ids:
                try:
                    ids = [UUID(x) for x in document_ids.split(",") if x.strip()]
                except ValueError:
                    raise HTTPException(status_code=400,
                                        detail="malformed document_ids")
            with session_factory() as session:
                pairs = _indexed_texts(session, ids)
            return Response(content=_anonymized_zip(pairs),
                            media_type="application/zip",
                            headers={"Content-Disposition":
                                     'attachment; filename="anonymized.zip"'})

    if search_index is not None:

        @app.get("/search", summary="Lexical (BM25) search", tags=["read"])
        def search(q: str, size: int = 10) -> dict:
            """Full-text search over the anonymized corpus."""
            hits = search_index.search(q, size=size)
            return {"query": q, "hits": [_hit(h) for h in hits]}

        @app.get("/export/ranking.csv", summary="Export a ranking as CSV",
                 tags=["export"])
        def export_ranking(query: str, k: int = 50) -> Response:
            """The lexical ranking for a query as CSV (Excel-openable): one row
            per hit with rank, document id and score — de-identified metadata
            only, never clear PII."""
            hits = search_index.search(query, size=k)
            return Response(content=_ranking_csv(hits), media_type="text/csv",
                            headers={"Content-Disposition":
                                     'attachment; filename="ranking.csv"'})

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
        if anonymizer is None and anonymizer_factory is None:
            from .openanonymiser_driver import OpenAnonymiserAnonymizer

            anonymizer = OpenAnonymiserAnonymizer()

        def _ingest_one(data: bytes) -> dict:
            """Drive one document to its terminal state; return its metadata
            (id, state, duration, counts). The un-redacted bytes never leave this
            frame and no exception it raises carries document text (fail-hard, no
            silent pass-through).

            Idempotent: content is addressed by sha256, so if a document with the
            same key is already in the SEARCH INDEX, skip it (no duplicate). The
            index — not the DB — is the source of truth for 'searchable', so this
            stays correct even if the index was recreated (those docs become
            eligible again). Re-running a directory therefore resumes cleanly,
            processing only what is actually missing from the index."""
            key = "documents/" + hashlib.sha256(data).hexdigest()
            if search_index.has_object_key(key):
                return {"state": "skipped"}
            with session_factory() as session:
                # Reversible mode binds a fresh session-scoped anonymizer (durable
                # keys + mapping store) per document; default mode uses the shared
                # irreversible driver.
                anon = anonymizer_factory(session) if anonymizer_factory else anonymizer
                doc = ingest(session, store, data)
                session.commit()
                document_id = doc.id
                state = process(session, document_id, store, anonymizer=anon,
                                search_index=search_index, embedder=embedder)
                session.commit()
                if state == State.UNPROCESSABLE_OCR:
                    # Scanned page: OCR to a text layer, then resume the straat.
                    recover(session, document_id, store)
                    session.commit()
                    state = process(session, document_id, store,
                                    anonymizer=anon,
                                    search_index=search_index, embedder=embedder)
                    session.commit()
                meta = _document_meta(session, document_id)
            return meta or {"document_id": str(document_id), "state": state.value}

        @app.post("/ingest", response_model=IngestResponse, tags=["write"],
                  summary="Ingest one or more PDFs through the full straat")
        def ingest_documents(
            files: list[UploadFile] = File(..., description="One or more PDF files"),
        ) -> IngestResponse:
            """Upload one or more PDFs. Each is driven through
            ingest → OCR recovery (if scanned) → anonymize → store → index and
            reported individually. A failing file does not abort the batch and
            never leaks document text (only its error class is returned).

            Deliberately a sync (not async) path operation: the pipeline is
            CPU/IO-heavy (GLiNER over HTTP, embeddings, DB), so FastAPI runs it in
            a worker thread and the event loop stays free to answer the liveness
            probe — otherwise a long batch starves /health and the pod is killed."""
            results: list[IngestResult] = []
            for f in files:
                data = f.file.read()
                if not data:
                    results.append(IngestResult(
                        filename=f.filename, state="error", error="empty upload"))
                    continue
                try:
                    meta = _ingest_one(data)
                    results.append(IngestResult(
                        filename=f.filename,
                        document_id=meta.get("document_id"),
                        state=meta.get("state"),
                        duration_ms=meta.get("duration_ms"),
                        counts=meta.get("counts") or None))
                except Exception as exc:  # fail-hard; carry no document text out
                    # A transient downstream outage (after in-pipeline retries)
                    # leaves the document resumable — not indexed, no clear PII —
                    # so report it 'retryable' and keep going; a permanent error
                    # is a terminal 'error'. Either way the batch is not aborted.
                    state = "retryable" if is_transient(exc) else "error"
                    results.append(IngestResult(
                        filename=f.filename, state=state,
                        error=type(exc).__name__))
            indexed = sum(1 for r in results if r.state == "indexed")
            return IngestResponse(total=len(results), indexed=indexed,
                                  results=results)

        # Backfill: re-run the reversible de-identify over already-processed
        # documents (e.g. a corpus first indexed irreversibly). Mounted only in
        # reversible mode (a session-scoped anonymizer factory present), because
        # reprocessing with the irreversible driver would be pointless.
        if anonymizer_factory is not None:

            def _reprocess_one(document_id: UUID) -> str:
                from .pipeline import reanonymize

                with session_factory() as session:
                    state = current_state(session, document_id)
                    if state not in (State.INDEXED, State.ANONYMIZED):
                        return "skipped"
                    anon = anonymizer_factory(session)
                    reanonymize(session, document_id, store, anonymizer=anon,
                                search_index=search_index, embedder=embedder)
                    session.commit()
                return "reanonymized"

            @app.post("/reprocess", response_model=ReprocessResponse,
                      tags=["write"],
                      summary="Backfill: re-de-identify documents reversibly")
            def reprocess(body: ReprocessRequest | None = None) -> ReprocessResponse:
                """Re-run the (reversible) de-identify over the given documents,
                or all INDEXED ones by default. Continue-on-failure: a transient
                outage leaves a document's existing entry intact and is counted
                'retryable'; a permanent error is 'failed'. Safe to re-run
                (idempotent) and long-running (GLiNER per document)."""
                ids: list[UUID] | None = None
                if body and body.document_ids:
                    try:
                        ids = [UUID(x) for x in body.document_ids]
                    except ValueError:
                        raise HTTPException(status_code=400,
                                            detail="malformed document_ids")
                with session_factory() as session:
                    if ids is None:
                        ids = [i for i in session.execute(
                            select(Document.id)).scalars()
                            if current_state(session, i) == State.INDEXED]
                counts = {"reanonymized": 0, "skipped": 0,
                          "retryable": 0, "failed": 0}
                for document_id in ids:
                    try:
                        counts[_reprocess_one(document_id)] += 1
                    except Exception as exc:  # never leaks text; entry left intact
                        counts["retryable" if is_transient(exc) else "failed"] += 1
                return ReprocessResponse(total=len(ids), **counts)

    # Key-gated reveal: turn a document's pseudonyms back into originals, but
    # only the PII types a grant authorises. Mounted only when a key provider and
    # grant store are supplied (durable keys arrive in a later cycle), so the
    # default deployment is unchanged. The reveal is audited by ``deanonymize``.
    if (session_factory is not None
            and (grant_store is not None or grant_store_factory is not None)
            and (key_provider is not None or key_provider_factory is not None)):

        @app.post("/documents/{document_id}/reveal", response_model=RevealResponse,
                  tags=["write"],
                  summary="Reveal a document's PII, gated per type by a grant")
        def reveal(document_id: UUID, body: RevealRequest, request: Request) -> RevealResponse:
            """Reveal the PII types a grant authorises; every other type stays
            pseudonymised. 404 if the document or grant is unknown, 403 if the
            grant is revoked, expired, or scoped to another document."""
            from .grants import authorize
            from .mapping_store import PostgresMappingStore
            from .pipeline import get_anonymized_text
            from .pseudonymizer import deanonymize

            now = datetime.now(timezone.utc)
            with session_factory() as session:
                # Session-scoped stores (durable keys, Postgres grant store) are
                # built per request from their factory; singletons win otherwise.
                gs = grant_store_factory(session) if grant_store_factory else grant_store
                kp = key_provider_factory(session) if key_provider_factory else key_provider

                grant = gs.get(body.grant_id)
                if grant is None:
                    raise HTTPException(status_code=404, detail="unknown grant")
                # A grant that authorises none of its own types here is revoked,
                # expired, or scoped to another document → explicit denial.
                if not authorize(grant, document_id, set(grant.allowed_types), now):
                    raise HTTPException(status_code=403, detail="grant not applicable")
                if current_state(session, document_id) is None:
                    raise HTTPException(status_code=404, detail="unknown document")
                pseudo_text = get_anonymized_text(session, document_id)
                if pseudo_text is None:
                    raise HTTPException(
                        status_code=409, detail="document not yet de-identified")
                requested = body.types if body.types else list(grant.allowed_types)
                allowed = authorize(grant, document_id, set(requested), now)
                # The authenticated caller (from api-key auth, if enabled) is
                # recorded distinctly from the grant recipient; None when auth
                # is off (tailnet-internal, grant_id as bearer capability).
                caller = getattr(request.state, "caller", None)
                extra_audit = {"grant_id": body.grant_id}
                if caller:
                    extra_audit["caller"] = caller
                revealed_text = deanonymize(
                    session, document_id, pseudo_text, kp,
                    PostgresMappingStore(session), actor=grant.recipient,
                    allowed_types=allowed,
                    extra_audit=extra_audit,
                )
                session.commit()
            requested_upper = {t.upper() for t in requested}
            return RevealResponse(
                document_id=str(document_id),
                revealed_text=revealed_text,
                revealed_types=sorted(allowed),
                withheld_types=sorted(requested_upper - allowed),
                grant_id=body.grant_id,
            )

    # Grant admin surface: issue / inspect / revoke reveal grants. Needs only a
    # grant store (no key provider) — mounts wherever grants are configured.
    if (session_factory is not None
            and (grant_store is not None or grant_store_factory is not None)):
        from pathlib import Path

        from .grants import issue_grant, revoke_grant

        def _resolve_audit() -> KeyLifecycleAudit:
            if key_audit is not None:
                return key_audit
            from .key_audit import JsonlKeyLifecycleAudit
            return JsonlKeyLifecycleAudit(
                Path(default_settings.key_lifecycle_audit_path))

        def _grant_response(g) -> GrantResponse:
            return GrantResponse(
                grant_id=g.grant_id,
                recipient=g.recipient,
                allowed_types=list(g.allowed_types),
                document_id=str(g.document_id) if g.document_id else None,
                status=g.status,
                created_at=g.created_at.isoformat(),
                revoked_at=g.revoked_at.isoformat() if g.revoked_at else None,
                expires_at=g.expires_at.isoformat() if g.expires_at else None,
            )

        def _grant_store(session):
            return grant_store_factory(session) if grant_store_factory else grant_store

        @app.post("/grants", response_model=GrantResponse, status_code=201,
                  tags=["admin"],
                  summary="Issue a reveal grant (operator/admin; no caller auth yet)")
        def grant_issue(body: GrantIssueRequest) -> GrantResponse:
            """Issue a grant permitting later reveal of the given PII types,
            optionally scoped to one document and/or expiring. Operator/admin
            surface: the API is tailnet-internal and the returned grant_id is a
            bearer capability — full caller authentication is a pending decision.
            The issue is recorded in the key-lifecycle audit stream."""
            doc_id = None
            if body.document_id:
                try:
                    doc_id = UUID(body.document_id)
                except ValueError:
                    raise HTTPException(status_code=400, detail="malformed document_id")
            expires = None
            if body.expires_at:
                try:
                    expires = datetime.fromisoformat(body.expires_at)
                except ValueError:
                    raise HTTPException(status_code=400,
                                        detail="malformed expires_at (ISO-8601)")
                if expires.tzinfo is None:
                    raise HTTPException(status_code=400,
                                        detail="expires_at must be timezone-aware")
            with session_factory() as session:
                grant = issue_grant(
                    _grant_store(session), _resolve_audit(),
                    recipient=body.recipient, allowed_types=body.allowed_types,
                    actor="operator", document_id=doc_id, expires_at=expires,
                )
                session.commit()
                return _grant_response(grant)

        @app.get("/grants/{grant_id}", response_model=GrantResponse, tags=["admin"],
                 summary="Inspect a grant")
        def grant_show(grant_id: str) -> GrantResponse:
            with session_factory() as session:
                grant = _grant_store(session).get(grant_id)
            if grant is None:
                raise HTTPException(status_code=404, detail="unknown grant")
            return _grant_response(grant)

        @app.post("/grants/{grant_id}/revoke", response_model=GrantResponse,
                  tags=["admin"], summary="Revoke a grant (idempotent)")
        def grant_revoke(grant_id: str) -> GrantResponse:
            with session_factory() as session:
                gs = _grant_store(session)
                if gs.get(grant_id) is None:
                    raise HTTPException(status_code=404, detail="unknown grant")
                revoke_grant(gs, _resolve_audit(), grant_id, actor="operator")
                session.commit()
                grant = gs.get(grant_id)
            return _grant_response(grant)

    return app


def _hit(h) -> dict:
    # Omit the raw vector from API responses; expose the useful fields only.
    return {"document_id": h.document_id, "score": h.score, "object_key": h.object_key}


def _ranking_csv(hits) -> str:
    """Render search hits as CSV text (stdlib; Excel-openable). De-identified
    metadata only — rank, document id, score, object key — never document text."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["rank", "document_id", "score", "object_key"])
    for rank, h in enumerate(hits, start=1):
        writer.writerow([rank, h.document_id, h.score, h.object_key or ""])
    return buf.getvalue()


def _anonymized_zip(pairs: list[tuple[str, str]]) -> bytes:
    """Build a ZIP whose entries are ``{document_id}.txt`` holding the stored
    de-identified text. In-memory (the corpus is small); deterministic order."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for document_id, text in pairs:
            zf.writestr(f"{document_id}.txt", text)
    return buf.getvalue()


def _indexed_texts(
    session: Session, ids: list[UUID] | None = None
) -> list[tuple[str, str]]:
    """(document_id, anonymized_text) for INDEXED documents (all, or the given
    subset), skipping any without stored text. Sorted by id for a stable ZIP."""
    if ids is None:
        ids = list(session.execute(select(Document.id)).scalars())
    out: list[tuple[str, str]] = []
    for document_id in ids:
        if current_state(session, document_id) != State.INDEXED:
            continue
        text = get_anonymized_text(session, document_id)
        if text is None:
            continue
        out.append((str(document_id), text))
    out.sort(key=lambda p: p[0])
    return out


def _document_meta(session: Session, document_id: UUID) -> dict | None:
    """Per-document metadata derived from the append-only audit chain: current
    state, total + per-step processing duration, PII redaction counts (the
    anonymize step), page/byte metrics, and the ordered step trail. Returns None
    when the document has no audit records."""
    records = session.execute(
        select(AuditRecord)
        .where(AuditRecord.document_id == document_id)
        .order_by(AuditRecord.seq)
    ).scalars().all()
    if not records:
        return None
    steps = []
    prev_ts = None
    for r in records:
        step_ms = ((r.ts - prev_ts).total_seconds() * 1000
                   if prev_ts is not None else None)
        steps.append({
            "step": r.step,
            "from_state": r.from_state,
            "to_state": r.to_state,
            "ts": r.ts.astimezone(timezone.utc).isoformat(),
            "duration_ms": round(step_ms, 1) if step_ms is not None else None,
            "payload": r.payload,
        })
        prev_ts = r.ts
    total_ms = (records[-1].ts - records[0].ts).total_seconds() * 1000
    counts = next((r.payload for r in records if r.step == "anonymize"), {})
    profile = next((r.payload for r in records if r.step == "profile"), {})
    doc = session.get(Document, document_id)
    return {
        "document_id": str(document_id),
        "object_key": doc.object_key if doc else None,
        "state": records[-1].to_state,
        "duration_ms": round(total_ms, 1),
        "counts": counts,
        "pages": profile.get("pages"),
        "bytes": profile.get("bytes"),
        "steps": steps,
    }
