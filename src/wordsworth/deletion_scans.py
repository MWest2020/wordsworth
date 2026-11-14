# SPDX-License-Identifier: MIT
"""The original scan of an OCR-recovered document, and what a deletion does
with it (`delete-removes-original-scan`, #454): the scan goes with its last
claimant, exactly as its data key does (`deletion_keys.py`).

Recovery (`recovery.py`) writes the OCR'd PDF under its own content-addressed
key and repoints `documents.object_key` at it; the scan it replaced is named
only in the recovering `ocr` audit record (`to_state = 'extractable'`), field
`old_object_key`. No column holds it. `scan_keys` reads that back, and is the
one helper `deletion_keys.doomed`, `dossier_locks.lock_members` and `plan`
below all use, so the locked set, the claimed set and the removed set cannot
drift apart (a document is recovered at most once, but the query below reads
"every scan this document's `ocr` records name" and does not assume one).
"""
from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import audit
from .models import AuditRecord
from .object_store import ObjectStore
from .states import State

#: The audit step of a scan removed when an already-deleted document is
#: deleted again -- `deleted` to `deleted`, like `deletion_keys`' `destroy-key`.
REMOVE_SCAN_STEP = "remove-original-scan"


def scan_keys(session: Session, document_ids: Sequence[UUID]) -> set[str]:
    """The distinct `old_object_key` of these documents' recovering `ocr`
    audit records -- the original scans their OCR recovery replaced."""
    if not document_ids:
        return set()
    return set(session.execute(
        select(AuditRecord.payload["old_object_key"].astext)
        .where(AuditRecord.step == "ocr",
               AuditRecord.to_state == State.EXTRACTABLE.value,
               AuditRecord.document_id.in_(document_ids))
    ).scalars().all())


def plan(session: Session, document_id: UUID, former_key: str,
        store: ObjectStore) -> list[str]:
    """The scan object keys this deletion removes: this document's scan
    keys, other than ``former_key`` (removed as the object, not as a scan),
    that are still in the store and claimed by no other document that is not
    deleted. Reads only -- the caller removes them."""
    from . import deletion_keys  # deferred: deletion_keys imports this module

    candidates = scan_keys(session, [document_id]) - {former_key}
    return [key for key in sorted(candidates)
            if store.exists(key)
            and not deletion_keys._object_claimed_elsewhere(session, document_id, key)]


def record_rerun(session: Session, document_id: UUID, *, actor: str,
                 original_scan: int) -> None:
    """The one record a rerun over an already-deleted document writes when
    it removes a scan: `deleted` to `deleted`, a count, never a key."""
    audit.append(session, document_id=document_id,
                 from_state=State.DELETED.value, to_state=State.DELETED.value,
                 step=REMOVE_SCAN_STEP,
                 payload={"actor": actor, "original_scan": original_scan})
