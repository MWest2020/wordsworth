"""Rotation orchestration: mint a new active key, escrow it, re-encrypt the
mappings onto it, and record the event in the append-only, hash-chained audit
trail. No document is touched — re-encryption is the separated-store payoff —
and no key material is ever logged (only key ids and a count).

Clever pitfall: the audit table is document-scoped (a document step machine),
but a rotation is a *global* key-management fact with no natural document. Rather
than weaken the core invariant table with a nullable ``document_id`` for one
event type, the rotation record is anchored to a fixed system document so it
joins the one global hash chain. Boring and auditable over clever."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from . import audit
from .escrow import Escrow
from .keys import Key, KeyProvider
from .mapping_store import MappingStore
from .models import Document

# Fixed sentinel document for system / key-management events.
SYSTEM_DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000000")
ROTATION_STEP = "key_rotation"
_ROTATION_STATE = "key_management"


def _ensure_system_document(session: Session) -> None:
    if session.get(Document, SYSTEM_DOCUMENT_ID) is None:
        session.add(
            Document(id=SYSTEM_DOCUMENT_ID, object_key="__system__/key-management")
        )
        session.flush()


def rotate_keys(
    session: Session,
    key_provider: KeyProvider,
    mapping_store: MappingStore,
    escrow: Escrow,
    actor: str,
) -> Key:
    """Rotate to a new active key and migrate mappings onto it.

    Order matters: escrow the new key *before* anything depends on it, then
    re-encrypt, then record. The caller owns the transaction (commit/rollback)."""
    old = key_provider.current_key()
    new = key_provider.rotate()
    escrow.deposit(new)
    count = mapping_store.reencrypt(old.id, new.id, key_provider)
    _ensure_system_document(session)
    audit.append(
        session,
        document_id=SYSTEM_DOCUMENT_ID,
        from_state=_ROTATION_STATE,
        to_state=_ROTATION_STATE,  # management event, not a state transition
        step=ROTATION_STEP,
        payload={
            "old_key_id": old.id,
            "new_key_id": new.id,
            "entries_reencrypted": count,
            "actor": actor,
        },
    )
    return new
