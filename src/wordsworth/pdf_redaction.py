# SPDX-License-Identifier: MIT
"""Box map computation, wired into `process` and `reanonymize` (design.md).

The box map needs each redacted value's clear text to locate it in the PDF.
That value is never stored anywhere in the clear — the ONE place it still
exists after anonymisation is encrypted in `pii_mappings`, keyed by the same
pseudonym the reversible driver just minted. So this module decrypts each of
the document's registered pseudonyms, exactly as a reveal does, but only to
hand the value to `build_box_map` in the same call stack — the result it
persists (`BoxMap`) carries page, rect and token only, never the value
(the same contract `AnonymizationResult` already keeps).

Nothing here runs without BOTH a key provider and a mapping store: the
irreversible driver keeps no mapping, so there is no value to decrypt, and a
document processed under it simply never gets a box map (no silent partial
result — `GET .../redacted.pdf` then answers 409, not a guess).
"""
from __future__ import annotations

import hashlib
import json
from uuid import UUID

from sqlalchemy.orm import Session

from . import audit, pseudonym_registry
from .crypto import decrypt
from .keys import KeyProvider
from .mapping_store import MappingStore
from .models import BoxMap
from .pdf_boxes import Box, Rect, ValueNotLocatedError, build_box_map
from .pseudonymizer import label_of


def _clear_values(
    session: Session, document_id: UUID, anonymized_text: str,
    key_provider: KeyProvider, mapping_store: MappingStore,
) -> list[tuple[str, str]]:
    """(token, clear_value) for every pseudonym this document's CURRENT
    anonymized text carries and this installation can still decrypt. A token
    whose mapping or key is gone is skipped — the same fail-open-on-reveal
    behaviour `_reveal` already has for an unresolvable token; it simply gets
    no box (and is then reported as not located, since it still occurs in the
    pypdf text)."""
    tokens = pseudonym_registry.registered(session, document_id) & \
        pseudonym_registry.tokens_in(anonymized_text)
    items: list[tuple[str, str]] = []
    for token in sorted(tokens):
        mapping = mapping_store.get(token)
        if mapping is None:
            continue
        try:
            key = key_provider.key(mapping.key_id)
        except KeyError:
            continue
        items.append((token, decrypt(key.material, mapping.ciphertext, mapping.nonce)))
    return items


def _serialise(boxes: list[Box]) -> list[dict]:
    return [{"page": b.page, "rect": [b.rect.x0, b.rect.y0, b.rect.x1, b.rect.y1],
            "token": b.token}
            for b in boxes]


def boxes_of(box_map: BoxMap) -> list[Box]:
    return [Box(row["page"], Rect(*row["rect"]), row["token"]) for row in box_map.boxes]


def redacted_cache_key(document_id: UUID, boxmap_hash: str) -> str:
    return f"redacted/{document_id}/{boxmap_hash}"


def compute_box_map(
    session: Session, document_id: UUID, pdf_bytes: bytes,
    anonymized_text: str, lists_hash: str | None,
    key_provider: KeyProvider, mapping_store: MappingStore,
) -> BoxMap | None:
    """Compute and persist the box map for one document, or — when a value
    cannot be located — write a `value-not-located` audit record and persist
    nothing (no partial box map, ever; the null-vector rule applied here).

    Returns the persisted `BoxMap`, or `None` when a value could not be
    located (the caller's transaction still commits the audit record)."""
    items = _clear_values(session, document_id, anonymized_text, key_provider, mapping_store)
    state = audit.current_state(session, document_id)
    try:
        boxes = build_box_map(pdf_bytes, anonymized_text, items)
    except ValueNotLocatedError as exc:
        audit.append(
            session, document_id=document_id,
            from_state=state.value, to_state=state.value,
            step="value-not-located",
            payload={"pii_type": label_of(exc.token),
                     "in_anonymized": exc.in_anonymized,
                     "in_positioned": exc.in_positioned},
        )
        return None
    payload = json.dumps(_serialise(boxes), sort_keys=True)
    boxmap_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    box_map = BoxMap(document_id=document_id, boxes=json.loads(payload),
                     lists_hash=lists_hash, boxmap_hash=boxmap_hash)
    session.merge(box_map)
    session.flush()
    return box_map
