"""The orchestration: guarded, atomic transitions + a resumable driver.

current_state is derived from the latest audit record. transition() guards the
edge and is idempotent (a no-op when the target is already the current state).
process() reads the current state and advances one document until terminal, so
it resumes correctly after a crash. Extract/anonymize/index are STUBS here — the
state and audit record exist; real work arrives in later changes.

The caller owns the transaction. transition()/register()/process() flush but do
not commit, so a transition and its audit record commit (or roll back) together.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import audit
from .anonymizer import Anonymizer, DeterministicAnonymizer
from .config import settings
from .extraction import ExtractionError, extract_text
from .models import AuditRecord, Document, DocumentText
from .profiling import ProfilingError, profile_pdf
from .search_index import SearchIndex
from .states import State, is_allowed


def current_state(session: Session, document_id: UUID) -> State | None:
    to_state = session.execute(
        select(AuditRecord.to_state)
        .where(AuditRecord.document_id == document_id)
        .order_by(AuditRecord.seq.desc())
        .limit(1)
    ).scalar_one_or_none()
    return State(to_state) if to_state else None


def transition(
    session: Session,
    document_id: UUID,
    to_state: State,
    *,
    step: str,
    payload: dict[str, Any] | None = None,
) -> AuditRecord | None:
    frm = current_state(session, document_id)
    if frm == to_state:
        return None  # idempotent no-op
    if not is_allowed(frm, to_state):
        raise ValueError(f"illegal transition {frm} -> {to_state}")
    return audit.append(
        session,
        document_id=document_id,
        from_state=frm.value if frm else None,
        to_state=to_state.value,
        step=step,
        payload=payload,
    )


def register(session: Session, object_key: str) -> Document:
    doc = Document(object_key=object_key)
    session.add(doc)
    session.flush()
    transition(session, doc.id, State.REGISTERED, step="register")
    return doc


def get_anonymized_text(session: Session, document_id: UUID) -> str | None:
    row = session.get(DocumentText, document_id)
    return row.anonymized_text if row else None


def _extract_or_fail(session: Session, document_id: UUID, pdf_bytes: bytes) -> str | None:
    try:
        return extract_text(pdf_bytes)
    except ExtractionError as exc:
        transition(session, document_id, State.FAILED, step="extract",
                   payload={"error": str(exc)})
        return None


def _default_index() -> SearchIndex:
    from .opensearch_index import OpenSearchIndex

    return OpenSearchIndex.from_config()


def process(
    session: Session,
    document_id: UUID,
    pdf_bytes: bytes,
    threshold: int | None = None,
    anonymizer: Anonymizer | None = None,
    search_index: SearchIndex | None = None,
) -> State:
    """Advance one document from its current state until terminal. Resumable.

    Extracted clear text is held in memory only; on resume from `extracted` it is
    re-derived from the source PDF, never read from a clear-text store.
    """
    threshold = threshold if threshold is not None else settings.born_digital_threshold
    anonymizer = anonymizer or DeterministicAnonymizer()
    state = current_state(session, document_id)
    text: str | None = None

    if state == State.REGISTERED:
        try:
            metric = profile_pdf(pdf_bytes, threshold)
        except ProfilingError as exc:
            transition(
                session, document_id, State.FAILED,
                step="profile", payload={"error": str(exc)},
            )
            return State.FAILED
        target = State.EXTRACTABLE if metric["born_digital"] else State.UNPROCESSABLE_OCR
        transition(
            session, document_id, target, step="profile",
            payload={k: metric[k] for k in ("chars", "pages", "bytes")},
        )
        state = target

    if state == State.EXTRACTABLE:
        text = _extract_or_fail(session, document_id, pdf_bytes)
        if text is None:
            return State.FAILED
        transition(session, document_id, State.EXTRACTED, step="extract",
                   payload={"chars": len(text)})
        state = State.EXTRACTED

    if state == State.EXTRACTED:
        if text is None:  # resume: re-derive deterministically, not from a store
            text = _extract_or_fail(session, document_id, pdf_bytes)
            if text is None:
                return State.FAILED
        result = anonymizer.anonymize(text)
        session.merge(DocumentText(document_id=document_id, anonymized_text=result.text))
        session.flush()
        transition(session, document_id, State.ANONYMIZED, step="anonymize",
                   payload=result.counts)
        state = State.ANONYMIZED

    if state == State.ANONYMIZED:
        anonymized = get_anonymized_text(session, document_id) or ""
        doc = session.get(Document, document_id)
        index = search_index or _default_index()
        index.ensure_ready()
        # Idempotent (upsert by id). If this raises (index down), it propagates:
        # nothing commits, the document stays `anonymized` and is retried later.
        index.index(str(document_id), anonymized, doc.object_key)
        transition(session, document_id, State.INDEXED, step="index",
                   payload={"chars": len(anonymized)})
        state = State.INDEXED

    return state
