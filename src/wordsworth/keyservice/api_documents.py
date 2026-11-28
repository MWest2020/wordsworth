"""``DELETE /v1/originals/{document_id}`` and ``DELETE /v1/documents/{document_id}``
(design.md "DELETE /v1/originals/{document_id}", "DELETE
/v1/documents/{document_id}"). Crypto-shredding and the document-deletion
chain: destroy data keys, registry rows and every mapping no other document
is registered for, delete every grant scoped to the document, and (for the
document deletion) leave a tombstone that keeps only id and domain.

Both write one key-lifecycle event (``lifecycle.append_lifecycle``, lock
4783) and one ``access_audit`` record (``audit.append_access``, lock 4782)
in the one transaction that does the deletion -- the two records are never
separable (design.md "Locks"). Locks follow ``docs/reference/lock-order.md``:
the registry lock (4781) is taken by the document deletion only, never by
the originals deletion."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import audit, known, lifecycle
from .config import settings
from .db import make_engine, make_session_factory
from .doc_keys import DocumentKeys
from .models import DocumentKeyRecord, DocumentToken, KnownDocument, PiiMapping
from .models_access import GrantRecord

router = APIRouter()


class DestroyedResponse(BaseModel):
    destroyed: int


class DocumentDeletionResponse(BaseModel):
    keys: int
    tokens: int
    mappings: int
    grants: int


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
    """One ``DocumentKeys`` per process (``api_originals.py``, ``api_open.py``):
    its unwrap cache stays warm across requests and across routers -- never
    rebuilt per call."""
    app = request.app
    if app.state.doc_keys is None:
        app.state.doc_keys = DocumentKeys(_transit_for(request))
    return app.state.doc_keys


def _destroy_keys(session: Session, document_id: UUID,
                  doc_keys: DocumentKeys | None) -> tuple[list[str], list[str]]:
    """Lock, then delete, every ``document_keys`` row for ``document_id``
    (the default of the open question in proposal.md: every row the service
    sealed for this document), ordered by ``object_key`` so two deletions
    take them in the same order. Evicts the destroyed object keys from the
    unwrap cache. Returns ``(object_keys, key_ids)``, both destroyed."""
    rows = session.execute(
        select(DocumentKeyRecord)
        .where(DocumentKeyRecord.document_id == document_id)
        .order_by(DocumentKeyRecord.object_key)
        .with_for_update()
    ).scalars().all()
    object_keys = [row.object_key for row in rows]
    key_ids = [row.key_id for row in rows]
    if object_keys:
        session.execute(sa_delete(DocumentKeyRecord)
                        .where(DocumentKeyRecord.object_key.in_(object_keys)))
    if doc_keys is not None:
        doc_keys.evict(object_keys)
    return object_keys, key_ids


def delete_originals(session: Session, document_id: UUID, *, actor: str,
                     doc_keys: DocumentKeys | None = None) -> int:
    """Destroy the document's data keys; idempotent (0 the second time).
    One lifecycle event and one access_audit record, same transaction."""
    object_keys, key_ids = _destroy_keys(session, document_id, doc_keys)
    lifecycle.append_lifecycle(
        session, action="keys_destroyed", actor=actor,
        payload={"document_id": str(document_id), "key_ids": key_ids})
    audit.append_access(
        session, event="delete_originals", service_caller=actor,
        document_id=document_id, payload={"destroyed": len(object_keys)})
    return len(object_keys)


def delete_document(session: Session, document_id: UUID, *, actor: str,
                    doc_keys: DocumentKeys | None = None) -> dict[str, int]:
    """Keys, registry rows, orphaned mappings and scoped grants go; a
    tombstone keeps id and domain, unless the document was never seen
    (design.md "DELETE /v1/documents/{document_id}"). Idempotent: already
    tombstoned, every count but ``grants`` is 0 and the tombstone is
    unchanged. One lifecycle event and one access_audit record, same
    transaction."""
    known.lock_registry(session)
    row = session.get(KnownDocument, document_id)

    object_keys, key_ids = _destroy_keys(session, document_id, doc_keys)

    tokens = sorted(session.execute(
        select(DocumentToken.token)
        .where(DocumentToken.document_id == document_id)
    ).scalars().all())
    orphan_mappings: list[str] = []
    if tokens:
        linked_elsewhere = set(session.execute(
            select(DocumentToken.token)
            .where(DocumentToken.token.in_(tokens),
                   DocumentToken.document_id != document_id)
        ).scalars().all())
        orphans = sorted(t for t in tokens if t not in linked_elsewhere)
        if orphans:
            orphan_mappings = session.execute(
                select(PiiMapping.pseudonym)
                .where(PiiMapping.pseudonym.in_(orphans))
                .order_by(PiiMapping.pseudonym)
                .with_for_update()
            ).scalars().all()
            session.execute(sa_delete(PiiMapping)
                            .where(PiiMapping.pseudonym.in_(orphan_mappings)))
        session.execute(sa_delete(DocumentToken)
                        .where(DocumentToken.document_id == document_id))

    grant_ids = sorted(session.execute(
        select(GrantRecord.grant_id).where(GrantRecord.document_id == document_id)
    ).scalars().all())
    if grant_ids:
        session.execute(sa_delete(GrantRecord)
                        .where(GrantRecord.grant_id.in_(grant_ids)))

    if row is not None and row.deleted_at is None:
        row.deleted_at = datetime.now(timezone.utc)

    counts = {"keys": len(object_keys), "tokens": len(tokens),
             "mappings": len(orphan_mappings), "grants": len(grant_ids)}
    lifecycle.append_lifecycle(
        session, action="document_deleted", actor=actor,
        payload={"document_id": str(document_id), "destroyed_key_ids": key_ids,
                "deleted_grant_ids": grant_ids})
    audit.append_access(
        session, event="delete_document", service_caller=actor,
        document_id=document_id, payload=counts)
    return counts


@router.delete("/v1/originals/{document_id}", response_model=DestroyedResponse)
def delete_originals_route(document_id: UUID, request: Request) -> DestroyedResponse:
    service_caller = request.state.service_caller
    session_factory = _session_factory(request)
    doc_keys = _doc_keys_for(request)
    with session_factory() as session:
        destroyed = delete_originals(session, document_id, actor=service_caller,
                                     doc_keys=doc_keys)
        session.commit()
    return DestroyedResponse(destroyed=destroyed)


@router.delete("/v1/documents/{document_id}", response_model=DocumentDeletionResponse)
def delete_document_route(document_id: UUID, request: Request) -> DocumentDeletionResponse:
    service_caller = request.state.service_caller
    session_factory = _session_factory(request)
    doc_keys = _doc_keys_for(request)
    with session_factory() as session:
        counts = delete_document(session, document_id, actor=service_caller,
                                 doc_keys=doc_keys)
        session.commit()
    return DocumentDeletionResponse(**counts)
