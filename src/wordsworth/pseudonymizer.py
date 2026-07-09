"""Reversible de-identification: stable keyed pseudonyms + a separated encrypted
mapping. `Pseudonymizer` satisfies the `Anonymizer` protocol, so it drops into
the pipeline's de-identify step as an alternative driver.

Deanonymization is an audited access event: it appends a `deanonymize` record to
the append-only, hash-chained audit trail, logging the pseudonyms and actor —
never the recovered clear values."""
from __future__ import annotations

import hashlib
import hmac
import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import audit, detectors
from .anonymizer import AnonymizationResult
from .crypto import decrypt, encrypt
from .keys import KeyProvider
from .mapping_store import MappingStore
from .models import AuditRecord

_PSEUDONYM_RE = re.compile(r"\[[A-Z]+:[0-9a-f]{8}\]")


def _token(key_material: bytes, label: str, value: str) -> str:
    msg = f"{label}:{value}".encode("utf-8")
    return hmac.new(key_material, msg, hashlib.sha256).hexdigest()[:8]


class Pseudonymizer:
    def __init__(self, key_provider: KeyProvider, mapping_store: MappingStore):
        self._keys = key_provider
        self._store = mapping_store

    def anonymize(self, text: str) -> AnonymizationResult:
        key = self._keys.current_key()
        counts: dict[str, int] = {}
        for label, pattern, validate in detectors.DETECTORS:

            def replacer(value: str, label: str = label) -> str:
                pseudonym = f"[{label.upper()}:{_token(key.material, label, value)}]"
                ciphertext, nonce = encrypt(key.material, value)
                self._store.put(pseudonym, ciphertext, nonce, key.id)
                return pseudonym

            text, counts[label] = detectors.substitute(text, pattern, replacer, validate)
        return AnonymizationResult(text=text, counts=counts)


def _current_state(session: Session, document_id: UUID) -> str | None:
    return session.execute(
        select(AuditRecord.to_state)
        .where(AuditRecord.document_id == document_id)
        .order_by(AuditRecord.seq.desc())
        .limit(1)
    ).scalar_one_or_none()


def deanonymize(
    session: Session,
    document_id: UUID,
    text: str,
    key_provider: KeyProvider,
    mapping_store: MappingStore,
    actor: str,
) -> str:
    """Recover originals from the store+key and audit-log the access."""
    state = _current_state(session, document_id)
    if state is None:
        raise ValueError("unknown document")
    revealed: list[str] = []

    def repl(match: re.Match[str]) -> str:
        pseudonym = match.group(0)
        mapping = mapping_store.get(pseudonym)
        if mapping is None:
            return pseudonym
        # Select the key by the mapping's stored key_id, so entries written
        # under any version (pre- or post-rotation) decrypt correctly.
        key = key_provider.key(mapping.key_id)
        revealed.append(pseudonym)
        return decrypt(key.material, mapping.ciphertext, mapping.nonce)

    restored = _PSEUDONYM_RE.sub(repl, text)
    audit.append(
        session,
        document_id=document_id,
        from_state=state,
        to_state=state,  # access event, not a state transition
        step="deanonymize",
        payload={"pseudonyms": sorted(set(revealed)), "actor": actor},
    )
    return restored
