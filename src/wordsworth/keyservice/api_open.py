"""``POST /v1/originals/{document_id}/open`` (design.md "POST
/v1/originals/{document_id}/open"). Sealed bytes in, plaintext out, for a
purpose from a fixed list; audited; a tampered key or envelope fails closed
and is audited, an unreachable Transit is a 503. Rate-limited per calling
service, after the purpose and query are validated, so the order is 401,
422, 429, then the rest of this table (``limits.py``, design.md "The rate
limit"). Seal lives in ``api_originals.py`` (design.md "Modules") -- this
file holds open only."""
from __future__ import annotations

from uuid import UUID

from cryptography.exceptions import InvalidTag
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select
from starlette.responses import Response

from wordsworth import originals_envelope

from . import audit, limits
from .config import settings
from .db import make_engine, make_session_factory
from .doc_keys import DocumentKeys, KeyBackendUnavailable, KeyDoesNotUnwrap
from .models import DocumentKeyRecord

router = APIRouter()

#: The readers of docs/reference/originals-readers.md, plus verification
#: (design.md "POST /v1/originals/{document_id}/open").
PURPOSES = frozenset({
    "process", "reanonymize", "ocr_recovery", "redacted_pdf", "reveal_pdf",
    "seal_verify",
})


def _session_factory(request: Request):
    app = request.app
    if app.state.session_factory is None:
        if app.state.engine is None:
            app.state.engine = make_engine()
        app.state.session_factory = make_session_factory(app.state.engine)
    return app.state.session_factory


def _transit_for(request: Request):
    app = request.app
    if app.state.transit_for is None:
        from wordsworth.transit import transit_factory
        app.state.transit_for = transit_factory(
            settings.openbao_url, settings.openbao_token)
    return app.state.transit_for


def _doc_keys_for(request: Request) -> DocumentKeys:
    """One ``DocumentKeys`` per process, so its unwrap cache stays warm across
    requests -- never rebuilt per call."""
    app = request.app
    if app.state.doc_keys is None:
        app.state.doc_keys = DocumentKeys(_transit_for(request))
    return app.state.doc_keys


@router.post("/v1/originals/{document_id}/open")
async def open_original(document_id: UUID, object_key: str, purpose: str,
                        request: Request) -> Response:
    body = await request.body()
    if len(body) > settings.max_original_bytes:
        raise HTTPException(
            413, detail="sealed object exceeds the configured size bound")
    if purpose not in PURPOSES:
        raise HTTPException(
            422, detail=f"purpose must be one of {sorted(PURPOSES)}")
    if not object_key:
        raise HTTPException(422, detail="object_key is required")

    service_caller = request.state.service_caller
    session_factory = _session_factory(request)

    decision = limits.check(
        session_factory, caller=service_caller,
        rate_per_minute=settings.open_rate_per_minute, burst=settings.open_burst)
    if not decision.allowed:
        raise HTTPException(
            429, detail="rate limit exceeded",
            headers={"Retry-After": str(decision.retry_after)})

    doc_keys = _doc_keys_for(request)

    with session_factory() as session:
        row = session.execute(
            select(DocumentKeyRecord)
            .where(DocumentKeyRecord.object_key == object_key)
        ).scalar_one_or_none()
        if row is None or row.document_id != document_id:
            audit.append_access(
                session, event="open_refused", service_caller=service_caller,
                document_id=document_id,
                payload={"object_key": object_key, "reason": "no_key"})
            session.commit()
            raise HTTPException(404, detail="no key for this object")

        try:
            key = doc_keys.unwrap(session, object_key)
        except KeyBackendUnavailable:
            raise HTTPException(503, detail="key service unavailable")
        except KeyDoesNotUnwrap:
            audit.append_access(
                session, event="open_failed", service_caller=service_caller,
                document_id=document_id,
                payload={"object_key": object_key, "reason": "unwrap"})
            session.commit()
            raise HTTPException(409, detail="sealed object does not open")

        try:
            plaintext = originals_envelope.open(
                key.material, key.key_id, object_key, body)
        except (InvalidTag, ValueError):
            audit.append_access(
                session, event="open_failed", service_caller=service_caller,
                document_id=document_id,
                payload={"object_key": object_key, "reason": "envelope"})
            session.commit()
            raise HTTPException(409, detail="sealed object does not open")

        audit.append_access(
            session, event="open", service_caller=service_caller,
            document_id=document_id,
            payload={"object_key": object_key, "purpose": purpose})
        session.commit()

    return Response(content=plaintext, media_type="application/octet-stream")
