"""Rotation orchestration: mint a new active key, escrow it, re-encrypt the
mappings onto it, and record the event in the separate append-only
key-lifecycle audit stream. No document is touched — re-encryption is the
separated-store payoff — and no key material is ever logged (only key ids and
a count).

Clever pitfall: the document audit table *is* the document state machine, and
its ``document_id`` is a mandatory FK to a real document. A key rotation is a
*global* key-management fact with no document; anchoring it to a sentinel
"system document" (the previous work-around) pollutes the state machine with a
phantom document whose lifecycle is really key rotations. Rotation events
therefore go to their own append-only stream (``key_audit``) and the document
hash-chain gains no record."""
from __future__ import annotations

from .escrow import Escrow
from .key_audit import KeyLifecycleAudit
from .keys import Key, KeyProvider
from .mapping_store import MappingStore


def rotate_keys(
    key_provider: KeyProvider,
    mapping_store: MappingStore,
    escrow: Escrow,
    key_audit: KeyLifecycleAudit,
    actor: str,
) -> Key:
    """Rotate to a new active key and migrate mappings onto it.

    Order matters: escrow the new key *before* anything depends on it, then
    re-encrypt, then record. The caller owns the mapping-store transaction
    (commit/rollback)."""
    old = key_provider.current_key()
    new = key_provider.rotate()
    escrow.deposit(new)
    count = mapping_store.reencrypt(old.id, new.id, key_provider)
    key_audit.rotation(
        old_key_id=old.id,
        new_key_id=new.id,
        entries_reencrypted=count,
        actor=actor,
    )
    return new
