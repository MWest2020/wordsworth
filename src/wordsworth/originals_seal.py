# SPDX-License-Identifier: MIT
"""`wordsworth-seal-originals` (ADR-0008, `originals-encrypt-existing`): seals
the existing corpus's legacy plaintext originals, one object at a time, below
the seam -- `put_original`'s rule 4 refuses to touch a legacy object on
purpose, so migrating it is this command's job, not the running service's.

Per object: mint (or reuse, on resume) its data key and commit that row with
`sealed_at` NULL before anything is written; seal the plaintext under a
temporary key `sealing/<sha256>`, verify it opens to the hash named in the
object key; only then overwrite `documents/<sha256>`, verify again, set
`sealed_at` and commit, then delete the temporary object. A failure before the
overwrite leaves the plaintext in place and the document reported `failed`;
a crash is resumed from whatever the key row and the store hold (design.md).

The original scan of a live document recovered by OCR (`old_object_key` in
its recovering `ocr` audit record, `deletion_scans.scan_keys`) is sealed the
same way and counted separately (`scans`, #473). A scan no longer in the
store -- gone between the listing and the read, or never there -- is reported
`gone`, never `failed` (#481): nothing was lost, there was nothing to seal.

The report, ``--dry-run``/``--verify`` and the CLI itself live in
`originals_seal_cli.py`, to stay under the 200-line file limit; this module is
the engine -- finding candidates and sealing one object -- that it drives."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import console_data, deletion_scans, originals_envelope
from .document_keys import DocumentKeyRecord, DocumentKeys
from .models import Document
from .object_store import ObjectStore, ObjectStoreError
from .states import State

TEMP_PREFIX = "sealing/"


def is_sealed(data: bytes) -> bool:
    """Not private: `originals_seal_cli.py`'s report needs it too."""
    return data[:len(originals_envelope.HEADER_MAGIC)] == originals_envelope.HEADER_MAGIC


def _hash_of(object_key: str) -> str:
    """The SHA-256 recorded for this object: the hex suffix of its
    content-addressed key (`documents/<sha256>`, the only shape an original's
    or a scan's object key has)."""
    return object_key.rsplit("/", 1)[-1]


@dataclass(frozen=True)
class Candidate:
    document_id: UUID
    object_key: str
    kind: str  # "original" | "scan"

    def as_dict(self) -> dict:
        return {"document_id": str(self.document_id), "object_key": self.object_key,
                "kind": self.kind}


def live_originals(session: Session) -> list[tuple[UUID, str]]:
    """``(document_id, object_key)`` for every document that is live right
    now (not superseded, not deleted) -- the one row per object key the
    partial unique index also picks out."""
    states = console_data.latest_state_subquery()
    rows = session.execute(
        select(Document.id, Document.object_key)
        .join(states, states.c.document_id == Document.id)
        .where(Document.superseded_by.is_(None),
               states.c.to_state != State.DELETED.value)
        .order_by(Document.id)
    ).all()
    return [(doc_id, key) for doc_id, key in rows]


def candidates(session: Session, store: ObjectStore, *,
               ids: set[UUID] | None = None) -> tuple[list[Candidate], list[Candidate]]:
    """``(work, gone)``: every live document's original and every live
    recovered document's scan still to seal, and the scans that are no longer
    in the store -- checked with `store.exists` here (#481), so a vanished
    scan is never added as a candidate in the first place."""
    originals = live_originals(session)
    if ids is not None:
        originals = [(doc_id, key) for doc_id, key in originals if doc_id in ids]

    work = [Candidate(doc_id, key, "original") for doc_id, key in originals]
    gone: list[Candidate] = []
    for doc_id, _ in originals:
        for scan_key in sorted(deletion_scans.scan_keys(session, [doc_id])):
            if store.exists(scan_key):
                work.append(Candidate(doc_id, scan_key, "scan"))
            else:
                gone.append(Candidate(doc_id, scan_key, "scan"))
    return work, gone


def seal_one(session_factory, store: ObjectStore, keys: DocumentKeys,
             document_id: UUID, object_key: str) -> dict:
    """Seal one object, resuming from whatever the key row and the store
    hold. Returns ``{"status": ..., ...}`` -- ``sealed``, ``already_sealed``,
    ``gone`` (absent from the store, never a failure), or ``failed`` (the
    plaintext stays, when it still can)."""
    sha = _hash_of(object_key)
    temp_key = f"{TEMP_PREFIX}{sha}"

    with session_factory() as session:
        row = session.get(DocumentKeyRecord, object_key)
        try:
            stored = store.get_raw(object_key)
        except ObjectStoreError:
            return {"status": "gone"}
        already_sealed = is_sealed(stored)

        if already_sealed and (row is None or row.sealed_at is not None):
            store.delete(temp_key)
            return {"status": "already_sealed"}
        if not already_sealed and row is not None and row.sealed_at is not None:
            # A downgrade: the row says sealed, the object says otherwise.
            # Repairing it by guess would be a silent fallback; leave it for
            # a human (object_store.SealedObjectError territory).
            return {"status": "failed", "reason": "downgraded"}

        if row is None:
            from .pipeline import document_domain  # deferred: avoids an import cycle

            domain = document_domain(session, document_id)
            key = keys.mint(session, document_id, object_key, domain)
            session.commit()
        else:
            key = keys.unwrap(session, object_key)

    # --- object-store phase: no open transaction while we write/verify -----
    if already_sealed:
        sealed_bytes = stored  # resumed after the overwrite, before `sealed_at`
    else:
        sealed_bytes = originals_envelope.seal(key.material, key.key_id, object_key, stored)
        store.put(temp_key, sealed_bytes)
        try:
            opened = originals_envelope.open(
                key.material, key.key_id, object_key, store.get_raw(temp_key))
            if hashlib.sha256(opened).hexdigest() != sha:
                raise ValueError("hash mismatch at the temporary key")
        except Exception:
            return {"status": "failed", "reason": "verify-failed"}
        store.put(object_key, sealed_bytes)

    try:
        opened_final = originals_envelope.open(
            key.material, key.key_id, object_key, store.get_raw(object_key))
        if hashlib.sha256(opened_final).hexdigest() != sha:
            raise ValueError("hash mismatch after the overwrite")
    except Exception:
        return {"status": "failed", "reason": "overwrite-verify-failed"}

    with session_factory() as session:
        row = session.get(DocumentKeyRecord, object_key)
        row.sealed_at = datetime.now(timezone.utc)
        session.commit()
    store.delete(temp_key)
    return {"status": "sealed", "bytes": len(opened_final)}
