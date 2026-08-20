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


def _label_of(pseudonym: str) -> str:
    """The PII type carried in a ``[LABEL:hash]`` token, e.g. ``PERSON``."""
    return pseudonym[1:pseudonym.index(":")]


def _reveal(
    text: str,
    allowed_types: set[str] | None,
    get_mapping,
    get_key,
) -> tuple[str, list[str]]:
    """Pure reveal substitution (no DB, no audit). Replace each token with its
    original only when its type is allowed AND its key resolves; otherwise leave
    the token untouched. Two independent gates: the ``allowed_types`` filter and
    cryptographic key availability. Returns (restored text, revealed tokens)."""
    revealed: list[str] = []

    def repl(match: re.Match[str]) -> str:
        pseudonym = match.group(0)
        if allowed_types is not None and _label_of(pseudonym) not in allowed_types:
            return pseudonym  # type not granted
        mapping = get_mapping(pseudonym)
        if mapping is None:
            return pseudonym
        try:
            # By the mapping's stored key_id, so entries under any version
            # (pre-/post-rotation) decrypt; a KeyError means the caller lacks
            # this type's key, so the token stays pseudonymised.
            key = get_key(mapping.key_id)
        except KeyError:
            return pseudonym
        revealed.append(pseudonym)
        return decrypt(key.material, mapping.ciphertext, mapping.nonce)

    return _PSEUDONYM_RE.sub(repl, text), revealed


class Pseudonymizer:
    def __init__(self, key_provider: KeyProvider, mapping_store: MappingStore):
        self._keys = key_provider
        self._store = mapping_store

    def anonymize(self, text: str) -> AnonymizationResult:
        counts: dict[str, int] = {}
        for label, pattern, validate in detectors.DETECTORS:
            # Each PII type is keyed under its own scope, so possessing a type's
            # key reveals only that type.
            key = self._keys.current_key(scope=label.upper())

            def replacer(value: str, label: str = label, key=key) -> str:
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
    allowed_types: set[str] | None = None,
) -> str:
    """Recover originals from the store+key and audit-log the access.

    ``allowed_types`` gates the reveal to a set of PII types (e.g. ``{"PERSON"}``);
    a token is revealed only when its type is allowed and its key resolves. When
    ``None``, every resolvable token is revealed (reveal-all)."""
    state = _current_state(session, document_id)
    if state is None:
        raise ValueError("unknown document")

    restored, revealed = _reveal(
        text, allowed_types, mapping_store.get, key_provider.key
    )
    audit.append(
        session,
        document_id=document_id,
        from_state=state,
        to_state=state,  # access event, not a state transition
        step="deanonymize",
        payload={
            "pseudonyms": sorted(set(revealed)),
            "types": sorted({_label_of(p) for p in revealed}),
            "requested_types": sorted(allowed_types) if allowed_types else "all",
            "actor": actor,
        },
    )
    return restored
