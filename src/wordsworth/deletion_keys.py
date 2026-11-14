# SPDX-License-Identifier: MIT
"""Crypto-shredding on delete (`originals-crypto-shred`, ADR-0008): deleting a
document destroys the wrapped data key of every object the deletion ends the
last claim on, in the same transaction as the rest of the deletion. A copy of
the sealed object that survives anywhere (a backup of the object store, a
replica) then opens under no key.

**A key follows its object.** The key goes exactly when the object goes: when
no other document row that is not deleted still points at that object key
(`_object_claimed_elsewhere`, the check the object removal uses too). A
superseded copy shares its object key with its survivor, so deleting the copy
leaves the survivor's key alone. A key row's `document_id` is not a reliable
owner (`put_original` re-points it on a re-ingest and leaves it on a reseal),
so the candidates are the row of the document's former object key plus every
row that carries its id (the scan of an OCR-recovered document), and the claim
check decides.

**Who deletes the rows.** `destroy` is plain SQL on the caller's session: no
key service, no `DocumentKeys`, so every caller shreds -- `wordsworth-delete`
too, which has a plain object store. A `DocumentKeys` only matters for its
own unwrap cache (`evict`); correctness on every replica comes from `unwrap`
checking the key row on every call, not from eviction.

**Two deletions at once.** A copy and its survivor deleted at the same moment
would each see the other as not yet deleted and each keep the object and the
key "for the other". `doomed` therefore locks the `documents` rows that carry
the candidate object keys (`SELECT ... FOR NO KEY UPDATE`, ordered by id, so
two deletions take them in the same order) before it reads who still claims
them. NO KEY UPDATE, not UPDATE: an audit append takes the chain's advisory
lock and then a KEY SHARE lock on the document row (the foreign key), which
FOR UPDATE would block while this deletion later waits for that advisory
lock -- a deadlock. Two NO KEY UPDATE locks still exclude each other.
The second deletion waits for the first to commit and then, under READ
COMMITTED (`db.py` sets no isolation level), reads the committed state.
"""
from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete as sa_delete
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from . import audit
from .audit import current_state
from .document_keys import DocumentKeyRecord, DocumentKeys
from .models import Document
from .states import State

#: The audit step of a key destroyed when an already-deleted document is
#: deleted again -- `deleted` to `deleted`, like `release_deleted`'s
#: `release-key`.
DESTROY_KEY_STEP = "destroy-key"


def _object_claimed_elsewhere(session: Session, document_id: UUID, object_key: str) -> bool:
    """Does some OTHER, not-yet-deleted document row still claim this object
    key? A superseded copy keeps its former key (one-document-per-object), so
    more than one row can point at the same bytes; removing them under one row
    must not take them out from under another that still needs them."""
    others = session.execute(
        select(Document.id).where(Document.object_key == object_key,
                                  Document.id != document_id)
    ).scalars().all()
    return any(current_state(session, other) != State.DELETED for other in others)


def _candidate_rows(document_id: UUID, former_key: str):
    return or_(DocumentKeyRecord.object_key == former_key,
               DocumentKeyRecord.document_id == document_id)


def _object_key(session: Session, document_id: UUID) -> str:
    return session.execute(select(Document.object_key)
                           .where(Document.id == document_id)).scalar_one()


def doomed(session: Session, document_id: UUID, *,
           lock: bool = True) -> tuple[str, list[str]]:
    """``(former_key, keys)``: the document's object key, read under the lock,
    and the object keys whose data key this deletion destroys -- the candidate
    rows (``former_key``'s, and every row carrying ``document_id``) that no
    other not-deleted document still claims. Runs before anything
    irreversible (the index entry, the object).

    With ``lock`` it locks first: the document's own row (by id, so a key
    that moved since it was read is still covered) and the rows of every
    candidate object key, in one statement ordered by id; then it reads the
    object key again and repeats once if it changed before the lock (the row
    is held after that, so it cannot change again); then it locks the key
    rows, so nothing else removes them before `destroy`. The row lock also
    stops an ingest from writing the object back (`ingest_lock.lock_live`,
    #452). A dry run (``lock=False``) takes no lock and waits for nothing."""
    locked_for = None
    while True:
        former_key = _object_key(session, document_id)
        if not lock or former_key == locked_for:
            break
        candidates = set(session.execute(
            select(DocumentKeyRecord.object_key)
            .where(_candidate_rows(document_id, former_key))
        ).scalars().all())
        session.execute(
            select(Document.id)
            .where(or_(Document.id == document_id,
                       Document.object_key.in_(sorted(candidates | {former_key}))))
            .order_by(Document.id)
            .with_for_update(key_share=True)
        ).all()
        locked_for = former_key
    rows = (select(DocumentKeyRecord.object_key)
            .where(_candidate_rows(document_id, former_key))
            .order_by(DocumentKeyRecord.object_key))
    keys = session.execute(rows.with_for_update() if lock else rows).scalars().all()
    return former_key, [key for key in keys
                        if not _object_claimed_elsewhere(session, document_id, key)]


def destroy(session: Session, object_keys: Sequence[str]) -> int:
    """Delete the key rows of ``object_keys``, in the caller's transaction.
    Raises when fewer rows go than were named: `doomed` locked them, so a
    difference means something is wrong, and a deletion must not report a
    key destroyed that it did not destroy. By then the index entry and the
    object may already be gone; the document is not marked deleted, and a
    rerun finishes the deletion."""
    if not object_keys:
        return 0
    gone = session.execute(
        sa_delete(DocumentKeyRecord)
        .where(DocumentKeyRecord.object_key.in_(list(object_keys)))
        .execution_options(synchronize_session="fetch")
    ).rowcount
    if gone != len(object_keys):
        raise RuntimeError(
            f"destroyed {gone} of {len(object_keys)} key rows; the document is "
            "not marked deleted, a rerun finishes the deletion")
    return gone


def record_rerun(session: Session, document_id: UUID, *, actor: str,
                 keys_destroyed: int) -> None:
    """The one record a rerun over an already-deleted document writes when it
    destroys keys: `deleted` to `deleted`, a count, never a key."""
    audit.append(session, document_id=document_id,
                 from_state=State.DELETED.value, to_state=State.DELETED.value,
                 step=DESTROY_KEY_STEP,
                 payload={"actor": actor, "keys_destroyed": keys_destroyed})


def keys_of(store) -> DocumentKeys | None:
    """The `DocumentKeys` an `OriginalsStore` carries, for evicting its unwrap
    cache after a delete; None for a plain store. Only the cache depends on
    it -- the key rows are destroyed either way."""
    from .originals_store import OriginalsStore

    return store.keys if isinstance(store, OriginalsStore) else None
