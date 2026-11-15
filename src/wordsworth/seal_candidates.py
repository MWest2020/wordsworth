# SPDX-License-Identifier: MIT
"""What `wordsworth-seal-originals` (originals-encrypt-existing) works on, and
the claim it re-checks under a lock before it touches an object.

**Candidates.** Every live document's original (not deleted, not superseded:
a superseded copy shares its object key with its survivor), plus the
original scan (`deletion_scans.scan_keys`) of every document that is not
deleted -- a superseded copy included, the spec counts it as not deleted --
each object key once.

**The claim under a lock.** A candidate list is read once, before a run that
can take hours; a deletion can commit at any point in it. `lock_claim` locks
the claimant's `documents` row FOR SHARE (`ingest_lock.lock_live`'s lock: it
conflicts with the FOR NO KEY UPDATE `deletion_keys.doomed` takes first, and
with nothing an ingest or an audit append takes) and says whether the
claimant still claims the object: not deleted, and its row still points at
it (an original) or its recovering `ocr` record still names it (a scan).
While that lock is held no deletion of the claimant can run, and a deletion
of any other document leaves a claimed object and its key alone
(`deletion_keys._object_claimed_elsewhere`). The seal run takes no audit-chain
advisory lock at all, so the codebase's lock order (row first, chain after)
cannot be inverted here."""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import deletion_scans, originals_envelope
from .audit import current_state
from .document_keys import DocumentKeyRecord
from .models import Document
from .object_store import ObjectStore, ObjectStoreError
from .states import State


def is_sealed(data: bytes) -> bool:
    return data[:len(originals_envelope.HEADER_MAGIC)] == originals_envelope.HEADER_MAGIC


@dataclass(frozen=True)
class Candidate:
    document_id: UUID
    object_key: str
    kind: str  # "original" or "scan"


def candidates(session: Session, ids: list[UUID] | None = None) -> list[Candidate]:
    """Every live document's original, then every scan of a document that is
    not deleted; an object key that is already a candidate is not repeated."""
    query = select(Document).order_by(Document.id)
    if ids is not None:
        query = query.where(Document.id.in_(ids))
    alive = [doc for doc in session.execute(query).scalars()
             if current_state(session, doc.id) != State.DELETED]
    out: list[Candidate] = []
    seen: set[str] = set()
    for doc in alive:
        if doc.superseded_by is None and doc.object_key not in seen:
            seen.add(doc.object_key)
            out.append(Candidate(doc.id, doc.object_key, "original"))
    for doc in alive:
        for key in sorted(deletion_scans.scan_keys(session, [doc.id])):
            if key not in seen and key != doc.object_key:
                seen.add(key)
                out.append(Candidate(doc.id, key, "scan"))
    return out


def lock_claim(session: Session, document_id: UUID, object_key: str, kind: str) -> bool:
    """Lock the claimant's row FOR SHARE, read fresh, and say whether it still
    claims ``object_key``: not deleted, and (``kind="original"``) its row
    points at it or (``kind="scan"``) its recovering `ocr` record names it.
    Held until the caller commits or rolls back."""
    doc = session.get(Document, document_id, populate_existing=True,
                      with_for_update={"read": True})
    if doc is None or current_state(session, document_id) == State.DELETED:
        return False
    if kind == "scan":
        return object_key in deletion_scans.scan_keys(session, [document_id])
    return doc.object_key == object_key


def key_row(session: Session, object_key: str) -> DocumentKeyRecord | None:
    """The key row as committed now -- a select with populate_existing, never
    an answer from the identity map."""
    return session.execute(
        select(DocumentKeyRecord).where(DocumentKeyRecord.object_key == object_key)
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()


def object_state(store: ObjectStore, object_key: str) -> tuple[str, int | None]:
    """``("sealed" | "legacy" | "missing", size)`` for this object key, read
    fresh from the store -- never from a row, which can disagree with it."""
    try:
        data = store.get_raw(object_key)
    except ObjectStoreError:
        return "missing", None
    return ("sealed" if is_sealed(data) else "legacy"), len(data)


def counts(store: ObjectStore, work: list[Candidate]) -> dict:
    out = {"objects": len(work), "sealed": 0, "legacy": 0, "missing": 0, "bytes": 0}
    for c in work:
        state, size = object_state(store, c.object_key)
        out[state] += 1
        out["bytes"] += size or 0
    return out
