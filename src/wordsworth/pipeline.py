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

import hashlib
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import audit
# Lives in `audit` (it reads nothing else); imported here so every caller of
# `pipeline.current_state` keeps working.
from .audit import current_state
from . import dossiers
from . import pseudonym_registry
from .anonymizer import Anonymizer, DeterministicAnonymizer
from .config import settings
from .embedder import Embedder
from .extraction import ExtractionError, extract_text
from .keys import DEFAULT_DOMAIN
from .models import AuditRecord, Document, DocumentText, DossierDocument
from .object_store import ObjectStore
from .profiling import ProfilingError, profile_pdf
from .retry import retry_transient
from .search_index import SearchIndex
from .states import State, is_allowed
from .structured_log import log_transition



def _last_ts(session: Session, document_id: UUID):
    return session.execute(
        select(AuditRecord.ts)
        .where(AuditRecord.document_id == document_id)
        .order_by(AuditRecord.seq.desc())
        .limit(1)
    ).scalar_one_or_none()


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
    prev_ts = _last_ts(session, document_id)
    record = audit.append(
        session,
        document_id=document_id,
        from_state=frm.value if frm else None,
        to_state=to_state.value,
        step=step,
        payload=payload,
    )
    duration_ms = (
        (record.ts - prev_ts).total_seconds() * 1000 if prev_ts is not None else None
    )
    log_transition(
        document_id=document_id,
        from_state=frm.value if frm else None,
        to_state=to_state.value,
        step=step,
        duration_ms=duration_ms,
        level="error" if to_state == State.FAILED else "info",
    )
    return record


def register(session: Session, object_key: str,
             domain: str = DEFAULT_DOMAIN, filename: str | None = None) -> Document:
    doc = Document(object_key=object_key, filename=filename)
    session.add(doc)
    session.flush()
    # The document's pseudonymisation domain is an audit fact from birth
    # (add-domain-keys); derived, never a mutable column.
    transition(session, doc.id, State.REGISTERED, step="register",
               payload={"domain": domain})
    return doc


def document_domain(session: Session, document_id: UUID) -> str:
    """The domain recorded at registration; legacy documents (no payload) are
    in the default domain."""
    payload = session.execute(
        select(AuditRecord.payload)
        .where(AuditRecord.document_id == document_id, AuditRecord.step == "register")
        .order_by(AuditRecord.seq)
        .limit(1)
    ).scalar_one_or_none() or {}
    return payload.get("domain") or DEFAULT_DOMAIN


def ingest(session: Session, store: ObjectStore, pdf_bytes: bytes,
           domain: str = DEFAULT_DOMAIN, filename: str | None = None,
           dossier: str | None = None) -> Document:
    """Store the PDF in object storage under a content-addressed key, then register
    the document against that key. `process` later fetches the bytes back by key —
    this closes the PoC shortcut of passing raw bytes across the pipeline seam.

    Content-addressing (sha256) makes the key deterministic, so re-ingesting the
    same bytes is idempotent at the object layer."""
    key = "documents/" + hashlib.sha256(pdf_bytes).hexdigest()
    store.put(key, pdf_bytes)
    # Content already ingested is one document, not a second. Delivering it into
    # another dossier adds a membership; that is the normal case, not an error.
    existing = live_document_for(session, key)
    doc = existing if existing is not None else register(session, key, domain, filename)
    if dossier:
        # Arriving in a case is an act too; "ingest" is who did it.
        dossiers.add(session, dossiers.ensure(session, dossier).id, doc.id,
                     actor="ingest")
    return doc


def live_document_for(session: Session, object_key: str) -> Document | None:
    """The document for this object that is not superseded, if any.

    Several rows can carry one `object_key` -- copies retired by
    one-document-per-object keep theirs -- so "the document for these bytes"
    is the live one, never simply the first row found.
    """
    return session.execute(
        select(Document).where(Document.object_key == object_key,
                               Document.superseded_by.is_(None))
    ).scalars().first()


def dossiers_of(session: Session, document_id: UUID) -> list[str]:
    """The dossiers this document belongs to, as strings for the index.

    Read at indexing time rather than passed down, because a document can gain a
    membership after it was first indexed (the same bytes delivered into another
    case) and the index has to learn that on the next pass.
    """
    return [str(r[0]) for r in session.execute(
        select(DossierDocument.dossier_id)
        .where(DossierDocument.document_id == document_id))]


def get_anonymized_text(session: Session, document_id: UUID) -> str | None:
    row = session.get(DocumentText, document_id)
    return row.anonymized_text if row else None


def _extract_or_fail(session: Session, document_id: UUID, pdf_bytes: bytes) -> str | None:
    try:
        return extract_text(pdf_bytes)
    except ExtractionError as exc:
        # Record the error TYPE only: a raw pypdf message is not guaranteed to be
        # free of document text, and this lands in the durable, exportable audit.
        transition(session, document_id, State.FAILED, step="extract",
                   payload={"error": type(exc).__name__})
        return None


def _default_index() -> SearchIndex:
    from .opensearch_index import OpenSearchIndex

    return OpenSearchIndex.from_config()


def _default_embedder() -> Embedder:
    from .embedder import OllamaEmbedder

    return OllamaEmbedder.from_config()


def process(
    session: Session,
    document_id: UUID,
    store: ObjectStore,
    threshold: int | None = None,
    anonymizer: Anonymizer | None = None,
    search_index: SearchIndex | None = None,
    embedder: Embedder | None = None,
) -> State:
    """Advance one document from its current state until terminal. Resumable.

    Source bytes are fetched from object storage by the document's recorded key —
    never received directly. Resume/re-processing re-fetches deterministically by
    the same key. Extracted clear text is held in memory only; on resume from
    `extracted` it is re-derived from those bytes, never read from a clear-text
    store.
    """
    threshold = threshold if threshold is not None else settings.born_digital_threshold
    anonymizer = anonymizer or DeterministicAnonymizer()
    doc = session.get(Document, document_id)
    state = current_state(session, document_id)
    text: str | None = None
    raw: bytes | None = None

    def pdf() -> bytes:
        # Lazy fetch-by-key: fetched once, only when a step actually needs bytes
        # (a terminal document does no work and never touches the store).
        nonlocal raw
        if raw is None:
            raw = store.get(doc.object_key)
        return raw

    if state == State.REGISTERED:
        try:
            metric = profile_pdf(pdf(), threshold)
        except ProfilingError as exc:
            transition(
                session, document_id, State.FAILED,
                step="profile", payload={"error": type(exc).__name__},
            )
            return State.FAILED
        target = State.EXTRACTABLE if metric["born_digital"] else State.UNPROCESSABLE_OCR
        transition(
            session, document_id, target, step="profile",
            payload={k: metric[k] for k in ("chars", "pages", "bytes")},
        )
        state = target

    if state == State.EXTRACTABLE:
        text = _extract_or_fail(session, document_id, pdf())
        if text is None:
            return State.FAILED
        transition(session, document_id, State.EXTRACTED, step="extract",
                   payload={"chars": len(text)})
        state = State.EXTRACTED

    if state == State.EXTRACTED:
        if text is None:  # resume: re-derive deterministically, not from a store
            text = _extract_or_fail(session, document_id, pdf())
            if text is None:
                return State.FAILED
        # A transient downstream blip is retried with backoff; if it persists the
        # error propagates and the document stays EXTRACTED (resumable) — never
        # indexed with clear PII. Fail-hard per attempt is unchanged.
        result = retry_transient(
            lambda: anonymizer.anonymize(text),
            settings.retry_attempts, settings.retry_base_delay,
        )
        session.merge(DocumentText(document_id=document_id, anonymized_text=result.text))
        # Welke pseudonymen bij dit document horen. Mag uit de uitvoer gelezen
        # worden omdat neutralise_foreign_tokens ervóór draait: wat er ná afloop
        # in staat, is hier gemunt.
        pseudonym_registry.register(session, document_id, result.text)
        session.flush()
        # Counts per type + per-layer confidence aggregates (add-detection-
        # confidence): aggregates only, never a value or an offset.
        transition(session, document_id, State.ANONYMIZED, step="anonymize",
                   payload={**result.counts, "detections": result.detections,
                            "lists_hash": result.lists_hash})
        state = State.ANONYMIZED

    if state == State.ANONYMIZED:
        anonymized = get_anonymized_text(session, document_id) or ""
        index = search_index or _default_index()
        embed = embedder or _default_embedder()
        # Failed embedding is a hard error (no null vector); it propagates like an
        # index outage: nothing commits, the document stays anonymized for retry.
        # Both external calls are retried on a transient blip (backoff); the
        # anonymized text carries no clear PII, so retrying is safe.
        vector = retry_transient(
            lambda: embed.embed([anonymized])[0],
            settings.retry_attempts, settings.retry_base_delay,
        )

        def _index() -> None:
            index.ensure_ready()
            # Idempotent (upsert by id) so a crash between index and commit is safe.
            index.index(str(document_id), anonymized, doc.object_key, vector=vector,
                        dossiers=dossiers_of(session, document_id))

        retry_transient(_index, settings.retry_attempts, settings.retry_base_delay)
        transition(session, document_id, State.INDEXED, step="index",
                   payload={"chars": len(anonymized), "dim": len(vector)})
        state = State.INDEXED

    return state


def lists_hash_of(session: Session, document_id: UUID) -> str | None:
    """De lijst-hash waaronder dit document het laatst is ge-de-identificeerd.

    Staat al in elk `anonymize`- en `reanonymize`-record. Daarmee is "dit
    document is al bijgewerkt" een **feit uit het spoor** in plaats van een
    tijdstempel die iemand moet onthouden: veranderen de lijsten, dan verandert
    de hash, en elk document dat nog de oude draagt is achterstallig.

    None = nooit onder een lijst verwerkt (of van vóór deze kolom). Dat telt als
    achterstallig zodra er lijsten zijn: liever een keer te veel werk dan een
    document dat stil de oude regels blijft dragen.
    """
    rij = session.execute(
        select(AuditRecord.payload)
        .where(AuditRecord.document_id == document_id,
               AuditRecord.step.in_(("anonymize", "reanonymize")))
        .order_by(AuditRecord.seq.desc()).limit(1)
    ).scalar_one_or_none()
    return (rij or {}).get("lists_hash")


def reanonymize(
    session: Session,
    document_id: UUID,
    store: ObjectStore,
    anonymizer: Anonymizer | None = None,
    search_index: SearchIndex | None = None,
    embedder: Embedder | None = None,
) -> State:
    """Re-run the de-identify step of an already-processed document through the
    CURRENT (injected) anonymizer, then re-index and overwrite the stored text.

    This backfills a corpus first indexed with the irreversible anonymizer into
    reversible pseudonyms: the reversible driver writes keyed tokens + encrypted
    mappings, so the index still holds only pseudonyms. Source text is re-derived
    from the object store by the document's key — never from a clear-text store.

    Fail-safe ordering: the new text is computed, embedded, and index-upserted
    BEFORE the stored ``DocumentText`` is overwritten. If any of those steps
    raises (a transient blip is retried first), the existing ``DocumentText`` and
    index entry are left untouched and the error propagates — a failure never
    blanks a document nor leaves clear PII. Only meaningful for INDEXED/ANONYMIZED
    documents; any other state is a no-op. Idempotent: stable keyed pseudonyms and
    an upsert-by-id index mean re-running yields the same text and one entry."""
    doc = session.get(Document, document_id)
    if doc is None:
        raise ValueError("unknown document")
    state = current_state(session, document_id)
    if state not in (State.INDEXED, State.ANONYMIZED):
        return state  # nothing to backfill (not yet de-identified / terminal-fail)

    anonymizer = anonymizer or DeterministicAnonymizer()
    index = search_index or _default_index()
    embed = embedder or _default_embedder()

    # Re-derive the source text from the stored bytes (never a clear-text store).
    text = extract_text(store.get(doc.object_key))

    # Compute + embed + re-index the NEW de-identified text first; a transient
    # blip is retried, a persistent failure propagates with the old entry intact.
    result = retry_transient(
        lambda: anonymizer.anonymize(text),
        settings.retry_attempts, settings.retry_base_delay,
    )
    vector = retry_transient(
        lambda: embed.embed([result.text])[0],
        settings.retry_attempts, settings.retry_base_delay,
    )

    def _index() -> None:
        index.ensure_ready()
        index.index(str(document_id), result.text, doc.object_key, vector=vector,
                    dossiers=dossiers_of(session, document_id))

    retry_transient(_index, settings.retry_attempts, settings.retry_base_delay)

    # Only now overwrite the stored text — after the index holds the new tokens.
    session.merge(DocumentText(document_id=document_id, anonymized_text=result.text))
    # Idem bij een herindexering: de nieuwe tokens komen erbij. Oude blijven
    # staan -- een registratie die krimpt onder een lopende reveal is een race,
    # geen waarborg.
    pseudonym_registry.register(session, document_id, result.text)
    session.flush()
    # An update/access event (from==to), like deanonymize: keeps the hash-chain
    # valid without an illegal state transition. Counts only, never clear values.
    audit.append(
        session,
        document_id=document_id,
        from_state=state.value,
        to_state=state.value,
        step="reanonymize",
        payload={"counts": result.counts, "detections": result.detections,
                 "lists_hash": result.lists_hash, "reanonymized": True},
    )
    return state
