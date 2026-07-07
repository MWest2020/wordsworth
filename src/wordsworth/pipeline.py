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
from .config import settings
from .models import AuditRecord, Document
from .profiling import ProfilingError, profile_pdf
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


def process(
    session: Session,
    document_id: UUID,
    pdf_bytes: bytes,
    threshold: int | None = None,
) -> State:
    """Advance one document from its current state until terminal. Resumable."""
    threshold = threshold if threshold is not None else settings.born_digital_threshold
    state = current_state(session, document_id)

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

    # Stub transitions — real work lands in later changes.
    if state == State.EXTRACTABLE:
        transition(session, document_id, State.EXTRACTED, step="extract", payload={"stub": True})
        state = State.EXTRACTED
    if state == State.EXTRACTED:
        transition(session, document_id, State.ANONYMIZED, step="anonymize", payload={"stub": True})
        state = State.ANONYMIZED
    if state == State.ANONYMIZED:
        transition(session, document_id, State.INDEXED, step="index", payload={"stub": True})
        state = State.INDEXED

    return state
