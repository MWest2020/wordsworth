"""The service's own key-lifecycle stream (design.md "The key-lifecycle
chain"): keys destroyed, documents deleted, grants revoked with them. Its
own hash-chained stream, under its own advisory lock (4783) -- never 4782
(``audit.py``'s access-audit chain, taken after this one) or wordsworth's
4771/4772. Same content and hash construction as wordsworth's
``key_audit_pg`` (the same canonical content of ``ts``, ``action``,
``actor``, ``payload``; ``hashing.compute_hash``; ``GENESIS_HASH``), so a
verifier that reads one reads the other.

It cannot be ``key_audit_pg.append``, which queries wordsworth's own model
on wordsworth's session (skeleton rule 3): this module appends to the
service's own ``KeyLifecycleEvent`` (``models_access.py``) instead."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from wordsworth.hashing import GENESIS_HASH, compute_hash

from .models_access import KeyLifecycleEvent

#: design.md "Locks", row 5 -- after the registry, key and mapping locks,
#: before the audit lock (4782, always last). Never wordsworth's 4771/4772.
LOCK_KEY = 4783


def _iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat()


def _content(*, ts: str, action: str, actor: str, payload: dict) -> str:
    """Deterministic JSON of one event -- the same construction as
    wordsworth's ``key_audit_pg._content``, so a verifier that reads one
    reads the other."""
    return json.dumps({"ts": ts, "action": action, "actor": actor,
                       "payload": payload},
                      sort_keys=True, separators=(",", ":"), default=str)


def append_lifecycle(session: Session, *, action: str, actor: str,
                     payload: dict[str, Any],
                     ts: datetime | None = None) -> KeyLifecycleEvent:
    """Chain one event onto the stream. The caller owns the transaction;
    flushes first, same reason as ``audit.append_access`` and
    ``known.lock_registry``: a pending row change must reach the database
    before the lock, not under it."""
    session.flush()
    session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": LOCK_KEY})
    # JSON-native before hashing: what is hashed must be exactly what JSONB
    # hands back, or an honest chain fails verification on a UUID.
    payload = json.loads(json.dumps(payload, default=str))
    ts = ts or datetime.now(timezone.utc)
    prev = session.execute(select(KeyLifecycleEvent.hash)
                           .order_by(KeyLifecycleEvent.seq.desc())
                           .limit(1)).scalar_one_or_none() or GENESIS_HASH
    event = KeyLifecycleEvent(
        ts=ts, action=action, actor=actor, payload=payload, prev_hash=prev,
        hash=compute_hash(prev, _content(ts=_iso(ts), action=action,
                                         actor=actor, payload=payload)))
    session.add(event)
    session.flush()
    return event


def verify_lifecycle_chain(session: Session) -> tuple[bool, int | None]:
    """(ok, first_bad_seq). Recomputes every hash from genesis."""
    prev = GENESIS_HASH
    for ev in session.execute(select(KeyLifecycleEvent)
                              .order_by(KeyLifecycleEvent.seq)).scalars():
        want = compute_hash(prev, _content(ts=_iso(ev.ts), action=ev.action,
                                           actor=ev.actor, payload=ev.payload))
        if ev.prev_hash != prev or ev.hash != want:
            return False, ev.seq
        prev = ev.hash
    return True, None
