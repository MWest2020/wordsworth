# SPDX-License-Identifier: MIT
"""`wordsworth-seal-originals --verify` (originals-encrypt-existing): what a
real run left behind, read fresh from the store and the key rows. Object keys
and ids only, never content; needs no key service.

It fails when a live document's original or a live recovered document's
scan is still legacy plaintext (the spec's pass condition), and also when a
sealed object cannot be opened by anyone: it has no key row, or its header
names a key id other than its row's, or when a live document's original
is missing from the store (that is data loss, not a pass), or when a live
document's original cannot be read (`unreadable`: a broken stream, a timeout
-- it may still be plaintext, so that is not a pass either). It lists, without
failing on them, pending objects (sealed, with `sealed_at` still NULL: a
rerun finishes them) and unreadable scans. A scan that is gone stays out of
the check (spec)."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from . import originals_envelope
from .object_store import ObjectStore
from .seal_candidates import candidates, key_row, probe


def _header_key_id(data: bytes) -> str | None:
    try:
        return originals_envelope.header_key_id(data)
    except ValueError:
        return None


def verify(session: Session, store: ObjectStore, ids: list[UUID] | None = None) -> dict:
    """``{"verified": bool, "legacy": [...], "no_key_row": [...],
    "key_id_mismatch": [...], "pending": [...], "missing": [...],
    "unreadable": [...]}``; each entry ``{"document_id", "object_key", "kind"}``.
    Reads a HEAD and the sealed header of each object, never the whole object."""
    out: dict[str, list] = {"legacy": [], "no_key_row": [], "key_id_mismatch": [],
                            "pending": [], "missing": [], "unreadable": []}
    for c in candidates(session, ids):
        entry = {"document_id": str(c.document_id), "object_key": c.object_key,
                 "kind": c.kind}
        state, _size, head = probe(store, c.object_key)
        if state == "missing":
            if c.kind == "original":  # a scan that is gone is left alone (spec)
                out["missing"].append(entry)
            continue
        if state in ("unreadable", "legacy"):
            out[state].append(entry)
            continue
        row = key_row(session, c.object_key)
        if row is None:
            out["no_key_row"].append(entry)
        elif _header_key_id(head) != row.key_id:
            out["key_id_mismatch"].append(entry)
        elif row.sealed_at is None:
            out["pending"].append(entry)
    unreadable_original = any(e["kind"] == "original" for e in out["unreadable"])
    verified = not (out["legacy"] or out["missing"] or out["no_key_row"]
                    or out["key_id_mismatch"] or unreadable_original)
    return {"verified": verified, **out}
