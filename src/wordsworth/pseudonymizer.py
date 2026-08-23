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
from typing import Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import audit, detectors
from .anonymizer import AnonymizationResult
from .crypto import decrypt, encrypt
from .keys import KeyProvider
from .mapping_store import MappingStore
from .models import AuditRecord
from .openanonymiser_driver import AnonymizationEngineError, Entity, detect_entities

# A detection seam: text -> entity spans. The default calls OpenAnonymiser; tests
# inject a fake so the reversible entity path is provable without the service.
DetectFn = Callable[[str], list[Entity]]

# Token labels are upper-cased PII types; allow digits/underscore so multi-word
# GLiNER types (e.g. PHONE_NUMBER) are matched and thus revealable.
_PSEUDONYM_RE = re.compile(r"\[[A-Z0-9_]+:[0-9a-f]{8}\]")

# Minimum length of a GLiNER entity value we will pseudonymise. Shorter spans are
# OCR/model noise (e.g. "ik", "re"), not PII; see _pseudonymize_entities.
_MIN_ENTITY_LEN = 3


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


class ReversibleAnonymizer:
    """`Anonymizer` driver that makes ALL PII reversible keyed pseudonyms: the
    deterministic detectors (BSN/IBAN/email) via `Pseudonymizer`, then GLiNER
    entities (PERSON, LOCATION, …) via a detection seam. Every value becomes a
    `[TYPE:hash]` token under that type's key, with the encrypted original in the
    mapping store — so the index holds only pseudonyms and any type is revealable
    by whoever holds its key. Fail-hard: if detection fails, it raises and never
    emits text with un-pseudonymised entities (no silent fallback)."""

    def __init__(
        self,
        key_provider: KeyProvider,
        mapping_store: MappingStore,
        detect: DetectFn | None = None,
    ):
        self._keys = key_provider
        self._store = mapping_store
        self._deterministic = Pseudonymizer(key_provider, mapping_store)
        self._detect = detect or detect_entities

    def anonymize(self, text: str) -> AnonymizationResult:
        result = self._deterministic.anonymize(text)  # keyed deterministic tokens
        body = result.text
        if not body.strip():
            return result
        try:
            entities = self._detect(body)
        except Exception as exc:
            # No pass-through: the text with clear entities never leaves this
            # frame, and the raised error carries none of it.
            raise AnonymizationEngineError(
                "entity detection failed; refusing to emit text with "
                "un-pseudonymised entities"
            ) from exc
        body, entity_counts = self._pseudonymize_entities(body, entities)
        counts = dict(result.counts)
        for label, n in entity_counts.items():
            counts[label] = counts.get(label, 0) + n
        return AnonymizationResult(text=body, counts=counts)

    def _pseudonymize_entities(
        self, text: str, entities: list[Entity]
    ) -> tuple[str, dict[str, int]]:
        """Replace every detected entity VALUE with a keyed token under its type's
        key — **offset-independent**.

        Earlier this sliced by the detector's ``(start, end)`` offsets; but the
        service reports offsets that need not line up with Python char slicing
        (byte- vs char-offsets on non-ASCII Dutch text, chunk-boundary spans),
        and a mismatch silently dropped the span, leaving clear PII in the index
        — a fail-*open* breach of the cardinal invariant. Instead we match the
        literal values in a single longest-preference pass (so all occurrences go,
        and a value inside a longer one is consumed by it), which cannot leak on
        an offset mismatch. Defense-in-depth: after substitution we strip inserted
        tokens and assert no detected value survives, else we fail hard — the
        index must never hold clear PII.

        Entity values shorter than ``_MIN_ENTITY_LEN`` are skipped: GLiNER emits
        spurious 1-2 char spans on OCR-noisy Dutch text (e.g. "ik", "re") that are
        not PII, and redacting them would both mangle the text (every occurrence
        of a common substring becomes a token) and, worse, guarantee a false
        survivor — such a fragment always recurs in ordinary text, tripping the
        fail-hard check and rejecting the whole document. Structured PII
        (BSN/IBAN/email) is handled by the deterministic pass regardless, and real
        entity PII (names/places/orgs) is >= 3 chars, so this cannot leak."""
        label_of: dict[str, str] = {}
        for e in entities:
            value = e.text
            if value and len(value.strip()) >= _MIN_ENTITY_LEN:
                label_of.setdefault(value, e.entity_type.lower())
        if not label_of:
            return text, {}

        counts: dict[str, int] = {}

        def repl(match: re.Match[str]) -> str:
            value = match.group(0)
            label = label_of[value]
            key = self._keys.current_key(scope=label.upper())
            pseudonym = f"[{label.upper()}:{_token(key.material, label, value)}]"
            ciphertext, nonce = encrypt(key.material, value)
            self._store.put(pseudonym, ciphertext, nonce, key.id)  # idempotent
            counts[label] = counts.get(label, 0) + 1
            return pseudonym

        # Match values only as WHOLE tokens — not as substrings inside larger
        # words — via non-word-char lookarounds. GLiNER emits fragment spans on
        # OCR-noisy Dutch text (e.g. "ene" in "voorzienen", "len" in "bepalen");
        # a bare substring match would both mangle ordinary words and, because
        # such a fragment recurs everywhere, guarantee a false survivor that
        # rejects the whole document. A real name/place is a whole word and is
        # still caught. Longest value first so a value containing a shorter one
        # wins; re.sub does not re-scan the tokens it inserts.
        values = sorted(label_of, key=len, reverse=True)
        alt = "|".join(re.escape(v) for v in values)
        text = re.compile(r"(?<!\w)(?:" + alt + r")(?!\w)").sub(repl, text)

        stripped = _PSEUDONYM_RE.sub("", text)  # remove inserted tokens
        for value in values:
            if re.search(r"(?<!\w)" + re.escape(value) + r"(?!\w)", stripped):
                raise AnonymizationEngineError(
                    "a detected entity value survived pseudonymisation; refusing "
                    "to emit text that may contain clear PII"
                )
        return text, counts


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
    extra_audit: dict | None = None,
) -> str:
    """Recover originals from the store+key and audit-log the access.

    ``allowed_types`` gates the reveal to a set of PII types (e.g. ``{"PERSON"}``);
    a token is revealed only when its type is allowed and its key resolves. When
    ``None``, every resolvable token is revealed (reveal-all). ``extra_audit``
    merges non-PII context into the access record (e.g. the ``grant_id`` that
    authorised it) — the caller is responsible for it carrying no clear value."""
    state = _current_state(session, document_id)
    if state is None:
        raise ValueError("unknown document")

    restored, revealed = _reveal(
        text, allowed_types, mapping_store.get, key_provider.key
    )
    payload = {
        "pseudonyms": sorted(set(revealed)),
        "types": sorted({_label_of(p) for p in revealed}),
        "requested_types": sorted(allowed_types) if allowed_types else "all",
        "actor": actor,
    }
    if extra_audit:
        payload.update(extra_audit)
    audit.append(
        session,
        document_id=document_id,
        from_state=state,
        to_state=state,  # access event, not a state transition
        step="deanonymize",
        payload=payload,
    )
    return restored
