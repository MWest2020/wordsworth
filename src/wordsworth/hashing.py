"""Pure hash-chain primitives. No database, no side effects — unit-testable.

The hashed content is the *semantic* record: document_id, from_state, to_state,
ts (normalised to UTC), step, payload. ``seq`` (DB-assigned) and the hash fields
themselves are excluded. A record's hash = sha256(prev_hash + canonical_content).
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

GENESIS_HASH = "0" * 64


def _ts(ts: datetime) -> str:
    if ts.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return ts.astimezone(timezone.utc).isoformat()


def canonical_content(
    *,
    document_id: UUID | str,
    from_state: str | None,
    to_state: str,
    ts: datetime,
    step: str,
    payload: dict[str, Any],
) -> str:
    """Deterministic JSON of the semantic record. Stable across a DB round-trip."""
    content = {
        "document_id": str(document_id),
        "from_state": from_state,
        "to_state": to_state,
        "ts": _ts(ts),
        "step": step,
        "payload": payload,
    }
    return json.dumps(
        content, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def compute_hash(prev_hash: str, content: str) -> str:
    return hashlib.sha256((prev_hash + content).encode("utf-8")).hexdigest()
