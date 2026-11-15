# SPDX-License-Identifier: MIT
"""`wordsworth-seal-originals --verify` (originals-encrypt-existing): what a
real run left behind, read fresh from the store and the key rows. Object keys
and ids only, never content; needs no key service.

It fails when a live document's original or a live recovered document's
scan is still legacy plaintext (the spec's pass condition), and also when a
sealed object cannot be opened by anyone: it has no key row, or its header
names a key id other than its row's, or when a live document's original
is missing from the store (that is data loss, not a pass). It lists, without
failing on them, pending objects (sealed, with `sealed_at` still NULL: a
rerun finishes them). A scan that is gone stays out of the check (spec)."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from . import originals_envelope
from .object_store import ObjectStore, ObjectStoreError
from .seal_candidates import candidates, is_sealed, key_row


def _header_key_id(data: bytes) -> str | None:
    try:
        return originals_envelope.header_key_id(data)
    except ValueError:
        return None


def verify(session: Session, store: ObjectStore, ids: list[UUID] | None = None) -> dict:
    """``{"verified": bool, "legacy": [...], "no_key_row": [...],
    "key_id_mismatch": [...], "pending": [...], "missing": [...]}``; each
    entry ``{"document_id", "object_key", "kind"}``."""
    out: dict[str, list] = {"legacy": [], "no_key_row": [], "key_id_mismatch": [],
                            "pending": [], "missing": []}
    for c in candidates(session, ids):
        entry = {"document_id": str(c.document_id), "object_key": c.object_key,
                 "kind": c.kind}
        try:
            data = store.get_raw(c.object_key)
        except ObjectStoreError:
            if c.kind == "original":  # a scan that is gone is left alone (spec)
                out["missing"].append(entry)
            continue
        if not is_sealed(data):
            out["legacy"].append(entry)
            continue
        row = key_row(session, c.object_key)
        if row is None:
            out["no_key_row"].append(entry)
        elif _header_key_id(data) != row.key_id:
            out["key_id_mismatch"].append(entry)
        elif row.sealed_at is None:
            out["pending"].append(entry)
    verified = not (out["legacy"] or out["missing"] or out["no_key_row"]
                    or out["key_id_mismatch"])
    return {"verified": verified, **out}
