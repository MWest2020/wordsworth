# SPDX-License-Identifier: MIT
"""How `wordsworth-seal-originals` (ADR-0008, originals-encrypt-existing)
seals one object without ever losing the plaintext, and without bringing a
deleted document back. Which objects, and the claim re-checked under a lock,
live in `seal_candidates.py`.

`put_original` is not used here: it refuses to touch a legacy object
(`originals_store.py` rule 4), which is right for ingest but not for this
migration. Per object, in two transactions, each under the claimant's row
lock (FOR SHARE, `seal_candidates.lock_claim`) and each re-checking the claim:

1. read the object and insert the `document_keys` row with `sealed_at` NULL,
   then commit -- the row exists before anything is written;
2. re-select the row; write the sealed bytes under `sealing/<sha256>` and
   verify they open to the recorded hash; only then overwrite
   `documents/<sha256>` and verify again; only then set `sealed_at` and
   commit; only then delete the temporary object.

A deletion that commits between the two, or before the first, makes the
claim fail: the object is reported `skipped_deleted`, `documents/<sha256>` is
never written, and a temporary copy no one else claims is removed (a claim
that moved without a deletion -- OCR recovery repointed the row -- is
`skipped_moved`, left for the next run). A deletion that starts while a lock
is held waits for the commit, then removes what the seal wrote, key row included.

A final key that does not verify (a corrupted write, a read error) is
repaired from the verified temporary copy, which is deleted only once the
final key verifies; if that fails too, the temporary copy is kept and the
object reported `failed`. A crash between the overwrite and the `sealed_at`
commit leaves a sealed object with no `sealed_at` -- `get_original` still
reads it, its guard keys off the header -- and a rerun verifies it (repairing
it from `sealing/<sha256>` if it does not open) and finishes the commit. An
object whose row has `sealed_at` and that carries the sealed header is done:
a rerun reads its header only, never the object (#491)."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from uuid import UUID

from cryptography.exceptions import InvalidTag

from . import originals_envelope
from .deletion_keys import _object_claimed_elsewhere
from .document_keys import DataKey, DocumentKeyRecord, DocumentKeys
from .object_store import ObjectMissingError, ObjectStore, ObjectStoreError
from .pipeline import current_state, document_domain
from .seal_candidates import is_sealed, key_row, lock_claim, read_full, sealed_header
from .states import State

TEMP_PREFIX = "sealing/"
_OBJECT_KEY = re.compile(r"documents/(?P<digest>[0-9a-f]{64})")


def _digest_of(object_key: str) -> str:
    match = _OBJECT_KEY.fullmatch(object_key)
    if not match:
        raise ValueError(f"not a content-addressed original key: {object_key!r}")
    return match.group("digest")


def _opened_size(key: DataKey, object_key: str, data: bytes, digest: str) -> int | None:
    """The plaintext size if ``data`` opens to ``digest``, else None."""
    try:
        opened = originals_envelope.open(key.material, key.key_id, object_key, data)
    except (InvalidTag, ValueError):
        return None
    return len(opened) if hashlib.sha256(opened).hexdigest() == digest else None


def _read_verified(store, key: DataKey, object_key: str, at: str, digest: str) -> int | None:
    try:
        data = store.get_raw(at)
    except ObjectStoreError:
        return None
    return _opened_size(key, object_key, data, digest)


def _restore_final(store, key: DataKey, object_key: str, temp_key: str, digest: str) -> int | None:
    """Put the temporary copy back at the final key if it opens to ``digest``,
    and verify the final key again. None when either check fails."""
    try:
        temp = store.get_raw(temp_key)
    except ObjectStoreError:
        return None
    if _opened_size(key, object_key, temp, digest) is None:
        return None
    store.put(object_key, temp)
    return _read_verified(store, key, object_key, object_key, digest)


def _failed(session, error: str) -> dict:
    session.rollback()
    return {"status": "failed", "error": error}


def _skipped(session, store, document_id: UUID, object_key: str, temp_key: str) -> dict:
    """The claim failed: write nothing at the final key. Deleted: remove a
    temporary copy unless another document still claims the object (then it
    may be that object's only good copy, for that claimant's run). Not
    deleted, the claim moved (OCR recovery repointed the row): leave it all
    for the next run, which finds the object under its new claim."""
    session.rollback()
    if current_state(session, document_id) != State.DELETED:
        session.rollback()
        return {"status": "skipped_moved"}
    if not _object_claimed_elsewhere(session, document_id, object_key):
        store.delete(temp_key)
    session.rollback()
    return {"status": "skipped_deleted"}


def _commit_sealed(session, store, row: DocumentKeyRecord, temp_key: str, size: int) -> dict:
    row.sealed_at = datetime.now(timezone.utc)
    session.flush()
    session.commit()
    store.delete(temp_key)
    return {"status": "sealed", "bytes": size}


def _resume(session, store, keys, row, object_key, temp_key, digest, stored) -> dict:
    """The object at the final key is sealed (still under the row lock)."""
    if row is None:
        return _failed(session, "sealed object has no key row")
    if row.sealed_at is not None:
        session.rollback()
        store.delete(temp_key)  # a crash after the commit can leave it behind
        return {"status": "already_sealed"}
    # The overwrite happened, the sealed_at commit did not. No plaintext left.
    key = keys.unwrap(session, object_key)
    size = _opened_size(key, object_key, stored, digest)
    if size is None:
        size = _restore_final(store, key, object_key, temp_key, digest)
    if size is None:
        return _failed(session, "sealed object does not open to the recorded hash "
                                "and no good copy is at the temporary key")
    return _commit_sealed(session, store, row, temp_key, size)


def seal_one(session, store: ObjectStore, keys: DocumentKeys, document_id: UUID,
             object_key: str, kind: str = "original") -> dict:
    """Seal one object. Returns ``{"status": ...}``: ``"sealed"`` (+ bytes),
    ``"already_sealed"``, ``"skipped_deleted"``, ``"skipped_moved"``,
    ``"gone"`` (a scan no longer in the store) or ``"failed"`` (+ a fixed
    ``"error"``: ``"missing"``, ``"unreadable"``, ...) -- never the document's
    bytes or anything derived from them. Raises on what it cannot classify (a
    key service down, a store write error); the caller reports that."""
    digest = _digest_of(object_key)
    temp_key = f"{TEMP_PREFIX}{digest}"

    # Transaction 1: read and mint under the lock.
    if not lock_claim(session, document_id, object_key, kind):
        return _skipped(session, store, document_id, object_key, temp_key)
    row = key_row(session, object_key)
    if row is not None and row.sealed_at is not None and sealed_header(store, object_key):
        return _resume(session, store, keys, row, object_key, temp_key, digest, b"")
    try:
        stored = read_full(store, object_key)  # the one full read, retried once
    except ObjectStoreError as exc:
        if kind == "scan":  # not there, or unreadable twice: `gone` (spec, #483)
            session.rollback()
            return {"status": "gone"}
        return _failed(session, "missing" if isinstance(exc, ObjectMissingError)
                       else "unreadable")
    if is_sealed(stored):
        return _resume(session, store, keys, row, object_key, temp_key, digest, stored)
    if row is not None and row.sealed_at is not None:
        return _failed(session, "key row is sealed but the object is plaintext")
    if row is None:
        keys.mint(session, document_id, object_key, document_domain(session, document_id))
    session.commit()  # the row before anything is written

    # Transaction 2: the claim again, then temp -> verify -> final -> verify.
    if not lock_claim(session, document_id, object_key, kind):
        return _skipped(session, store, document_id, object_key, temp_key)
    row = key_row(session, object_key)
    if row is None:
        return _failed(session, "key row gone before the write")
    if row.sealed_at is not None:
        session.rollback()
        return {"status": "already_sealed"}
    key = keys.unwrap(session, object_key)
    sealed = originals_envelope.seal(key.material, key.key_id, object_key, stored)
    store.put(temp_key, sealed)
    if _read_verified(store, key, object_key, temp_key, digest) is None:
        store.delete(temp_key)
        return _failed(session, "sealed copy does not open to the recorded hash")

    try:
        store.put(object_key, sealed)
        size = _read_verified(store, key, object_key, object_key, digest)
    except Exception:  # repaired from the verified temporary copy below
        size = None
    if size is None:
        size = _restore_final(store, key, object_key, temp_key, digest)
    if size is None:
        return _failed(session, "sealed object at the final key does not verify; "
                                "the verified copy at the temporary key is kept")
    return _commit_sealed(session, store, row, temp_key, size)
