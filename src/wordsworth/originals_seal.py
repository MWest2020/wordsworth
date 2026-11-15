# SPDX-License-Identifier: MIT
"""The per-object mechanics `wordsworth-seal-originals` (ADR-0008,
originals-encrypt-existing) drives: which objects need sealing, and how one
of them gets sealed without ever losing the plaintext.

`put_original` is not used here: it refuses to touch a legacy object
(`originals_store.py` rule 4), which is right for ingest but not for this
migration. Per object: insert the `document_keys` row with `sealed_at` NULL
and commit it before anything is written; write the sealed bytes under a
temporary key `sealing/<sha256>`, verify they open to the recorded hash; only
then overwrite `documents/<sha256>` and verify again; only then set
`sealed_at` and commit; only then delete the temporary object. A crash
between the overwrite and that commit leaves a sealed object with no
`sealed_at` yet -- `get_original` still reads it fine, its guard keys off the
header, not the column -- and a rerun finds exactly that state and finishes
it without touching the (already gone) plaintext again."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from . import deletion_scans, originals_envelope
from .document_keys import DocumentKeyRecord, DocumentKeys
from .models import Document
from .object_store import ObjectStore, ObjectStoreError
from .pipeline import current_state, document_domain
from .states import State

TEMP_PREFIX = "sealing/"
_OBJECT_KEY = re.compile(r"documents/(?P<digest>[0-9a-f]{64})")


def _is_sealed(data: bytes) -> bool:
    return data[:len(originals_envelope.HEADER_MAGIC)] == originals_envelope.HEADER_MAGIC


def _digest_of(object_key: str) -> str:
    match = _OBJECT_KEY.fullmatch(object_key)
    if not match:
        raise ValueError(f"not a content-addressed original key: {object_key!r}")
    return match.group("digest")


@dataclass(frozen=True)
class Candidate:
    document_id: UUID
    object_key: str
    kind: str  # "original" or "scan"


def candidates(session, ids: list[UUID] | None = None) -> list[Candidate]:
    """Every live document's original, plus the original scan of a live
    document recovered by OCR (`kind="scan"`), skipping a scan that still is
    the document's own current object key."""
    query = select(Document).where(Document.superseded_by.is_(None))
    if ids is not None:
        query = query.where(Document.id.in_(ids))
    out = []
    for doc in session.execute(query).scalars():
        if current_state(session, doc.id) == State.DELETED:
            continue
        out.append(Candidate(doc.id, doc.object_key, "original"))
        scans = deletion_scans.scan_keys(session, [doc.id]) - {doc.object_key}
        out.extend(Candidate(doc.id, key, "scan") for key in sorted(scans))
    return out


def object_state(store: ObjectStore, object_key: str) -> tuple[str, int | None]:
    """``("sealed" | "legacy" | "missing", size)`` for this object key, read
    fresh from the store -- never from a row, which can disagree with it."""
    try:
        data = store.get_raw(object_key)
    except ObjectStoreError:
        return "missing", None
    return ("sealed" if _is_sealed(data) else "legacy"), len(data)


def counts(store: ObjectStore, work: list[Candidate]) -> dict:
    out = {"objects": len(work), "sealed": 0, "legacy": 0, "missing": 0, "bytes": 0}
    for c in work:
        state, size = object_state(store, c.object_key)
        out[state] += 1
        out["bytes"] += size or 0
    return out


def seal_one(session, store: ObjectStore, keys: DocumentKeys,
            document_id: UUID, object_key: str) -> dict:
    """Seal one object: never touches the plaintext before a sealed, hashed
    copy has been verified to open correctly. Returns ``{"status": ...}``,
    ``"sealed"``/``"already_sealed"``/``"failed"`` (+ ``"error"``), never the
    document's bytes or any value derived from its content."""
    digest = _digest_of(object_key)
    temp_key = f"{TEMP_PREFIX}{digest}"
    row = session.get(DocumentKeyRecord, object_key)
    try:
        stored = store.get_raw(object_key)
    except ObjectStoreError:
        return {"status": "failed", "error": "missing"}

    if _is_sealed(stored):
        if row is None:
            return {"status": "failed", "error": "sealed object has no key row"}
        if row.sealed_at is not None:
            return {"status": "already_sealed"}
        # Resumed: the overwrite committed, sealed_at did not. Verify, then
        # only finish the commit -- there is no plaintext left to protect.
        try:
            key = keys.unwrap(session, object_key)
            opened = originals_envelope.open(key.material, key.key_id, object_key, stored)
            if hashlib.sha256(opened).hexdigest() != digest:
                raise ValueError("sealed object does not open to the recorded hash")
        except Exception as exc:
            return {"status": "failed", "error": str(exc)}
        row.sealed_at = datetime.now(timezone.utc)
        session.flush()
        session.commit()
        store.delete(temp_key)
        return {"status": "sealed", "bytes": len(opened)}

    if row is not None and row.sealed_at is not None:
        return {"status": "failed", "error": "key row is sealed but the object is plaintext"}

    if row is None:
        key = keys.mint(session, document_id, object_key, document_domain(session, document_id))
        session.commit()  # the row before anything is written
    else:
        key = keys.unwrap(session, object_key)

    sealed = originals_envelope.seal(key.material, key.key_id, object_key, stored)
    store.put(temp_key, sealed)
    try:
        reread = store.get_raw(temp_key)
        opened = originals_envelope.open(key.material, key.key_id, object_key, reread)
        if hashlib.sha256(opened).hexdigest() != digest:
            raise ValueError("sealed copy does not open to the recorded hash")
    except Exception as exc:
        store.delete(temp_key)
        return {"status": "failed", "error": str(exc)}

    store.put(object_key, sealed)
    final = store.get_raw(object_key)
    opened_final = originals_envelope.open(key.material, key.key_id, object_key, final)
    if hashlib.sha256(opened_final).hexdigest() != digest:
        return {"status": "failed",
               "error": "sealed object at the final key does not open to the recorded hash"}

    row = session.get(DocumentKeyRecord, object_key)
    row.sealed_at = datetime.now(timezone.utc)
    session.flush()
    session.commit()
    store.delete(temp_key)
    return {"status": "sealed", "bytes": len(stored)}
