"""``POST /v1/originals/{document_id}/seal`` (design.md "POST
/v1/originals/{document_id}/seal"). Bytes in, sealed bytes and ``X-Key-Id``
out; one data key per object key, never a second one. Open lives in
``api_open.py`` (design.md "Modules") -- this file holds seal only."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select
from starlette.responses import Response

from wordsworth import originals_envelope

from . import audit, known
from .config import settings
from .db import make_engine, make_session_factory
from .doc_keys import DocumentKeys
from .models import DocumentKeyRecord

router = APIRouter()


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


@router.post("/v1/originals/{document_id}/seal")
async def seal(document_id: UUID, domain: str, object_key: str,
               request: Request) -> Response:
    body = await request.body()
    if len(body) > settings.max_original_bytes:
        raise HTTPException(
            413, detail="original exceeds the configured size bound")
    if not domain or "/" in domain:
        raise HTTPException(
            422, detail="domain must be non-empty and contain no '/'")
    if not object_key:
        raise HTTPException(422, detail="object_key is required")

    service_caller = request.state.service_caller
    session_factory = _session_factory(request)
    doc_keys = _doc_keys_for(request)

    with session_factory() as session:
        known.lock_registry(session)
        try:
            known.ensure_known(session, document_id, domain)
        except known.DomainConflict:
            raise HTTPException(
                409, detail="document is registered in another domain")
        except known.DocumentDeleted:
            raise HTTPException(410, detail="document deleted")

        row = session.execute(
            select(DocumentKeyRecord)
            .where(DocumentKeyRecord.object_key == object_key)
            .with_for_update()
        ).scalar_one_or_none()
        if row is not None and row.document_id != document_id:
            raise HTTPException(
                409, detail="object key belongs to another document")

        try:
            if row is None:
                key = doc_keys.mint(session, document_id, object_key, domain)
                minted = True
            else:
                key = doc_keys.unwrap(session, object_key)
                minted = False
        except Exception as exc:
            raise HTTPException(503, detail="key service unavailable") from exc

        sealed = originals_envelope.seal(key.material, key.key_id, object_key, body)

        row = session.get(DocumentKeyRecord, object_key)
        row.sealed_at = datetime.now(timezone.utc)
        session.flush()

        audit.append_access(
            session, event="seal", service_caller=service_caller,
            document_id=document_id,
            payload={"object_key": object_key, "key_id": key.key_id,
                    "minted": minted})

        session.commit()

    return Response(content=sealed, media_type="application/octet-stream",
                    headers={"X-Key-Id": key.key_id})
