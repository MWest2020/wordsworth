"""The service's own access-audit stream (design.md "The audit writer").
``append_access`` is under its own advisory lock (4782), taken last
(``docs/reference/lock-order.md``) -- the audit is the terminal leaf,
nothing is taken after it. Pure SQL on the service's own session, so no
wordsworth model is queried; the hash-chain primitives (``compute_hash``,
``GENESIS_HASH``) are wordsworth's own, reused as-is (they read no
settings and touch no model)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from wordsworth.hashing import GENESIS_HASH, compute_hash

from .models_access import AccessAudit

#: design.md "Locks", row 6 -- last, after the registry lock (4781) is
#: released by commit. Never wordsworth's 4771, never this service's own
#: key-lifecycle lock (4783, ``key-service-delete``).
LOCK_KEY = 4782


def _iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat()


def _content(*, ts: str, event: str, document_id: str | None,
             service_caller: str, caller: str | None, payload: dict) -> str:
    """Deterministic JSON of one record. Stable across a database round trip."""
    return json.dumps(
        {"ts": ts, "event": event, "document_id": document_id,
         "service_caller": service_caller, "caller": caller, "payload": payload},
        sort_keys=True, separators=(",", ":"), default=str)


def append_access(session: Session, *, event: str, service_caller: str,
                  document_id: UUID | None, payload: dict[str, Any],
                  caller: str | None = None,
                  ts: datetime | None = None) -> AccessAudit:
    """Chain one record onto the stream. The caller owns the transaction."""
    session.flush()
    session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": LOCK_KEY})
    # JSON-native before hashing: what is hashed must be exactly what JSONB
    # hands back, or an honest chain fails verification on a UUID.
    payload = json.loads(json.dumps(payload, default=str))
    ts = ts or datetime.now(timezone.utc)
    document_id_str = str(document_id) if document_id is not None else None
    prev = session.execute(
        select(AccessAudit.hash).order_by(AccessAudit.seq.desc()).limit(1)
    ).scalar_one_or_none() or GENESIS_HASH
    content = _content(ts=_iso(ts), event=event, document_id=document_id_str,
                       service_caller=service_caller, caller=caller, payload=payload)
    record = AccessAudit(
        ts=ts, event=event, document_id=document_id, service_caller=service_caller,
        caller=caller, payload=payload, prev_hash=prev,
        hash=compute_hash(prev, content))
    session.add(record)
    session.flush()
    return record


def verify_access_chain(session: Session) -> tuple[bool, int | None]:
    """(ok, first_bad_seq). Recomputes every hash from genesis."""
    prev = GENESIS_HASH
    for rec in session.execute(
            select(AccessAudit).order_by(AccessAudit.seq)).scalars():
        document_id_str = str(rec.document_id) if rec.document_id is not None else None
        content = _content(ts=_iso(rec.ts), event=rec.event,
                           document_id=document_id_str,
                           service_caller=rec.service_caller, caller=rec.caller,
                           payload=rec.payload)
        if rec.prev_hash != prev or rec.hash != compute_hash(prev, content):
            return False, rec.seq
        prev = rec.hash
    return True, None
