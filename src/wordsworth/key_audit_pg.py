# SPDX-License-Identifier: MIT
"""The key-lifecycle stream, in PostgreSQL (key-audit-in-postgres).

Grants issued and revoked, roles changed, dossiers renamed, keys rotated: the
facts that decide who may see what without touching a document. Until
2026-09-23 they went to a JSONL file in the api pod's `/tmp`, an `emptyDir`.
Measured that day, the file held exactly one event; everything before the last
restart was gone. "Append-only" was true and meaningless.

Three properties, each for a reason:

- **In the caller's transaction.** The driver is bound to the session that makes
  the change, so the event and the change commit together or not at all. A
  driver with its own session would let a revoke commit while its record failed
  — and that is the gap this module exists to close.
- **Append-only at the schema level**, by the trigger in `db.py`.
- **Hash-chained**, its own chain beside the document chain. The table starts
  empty, which makes now the cheapest moment the chain will ever have;
  `key_audit_export.py` named the missing chain as a known weakness.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .hashing import GENESIS_HASH, compute_hash
from .key_audit import (DOSSIER_RENAMED_ACTION, GRANT_ISSUED_ACTION,
                        GRANT_REVOKED_ACTION, ROLE_ACTION, ROTATION_ACTION,
                        STREAM)
from .models import KeyLifecycleEvent

#: Not the document chain's key (4771): two chains, two locks. Sharing one would
#: couple document throughput to authorisation writes for no benefit.
_LOCK_KEY = 4772


#: Keys an exported line adds around the payload. Payload keys never use them.
_ENVELOPE = frozenset({"seq", "ts", "stage", "action", "actor", "prev_hash", "hash"})


def _iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat()


def _content(*, ts: str, action: str, actor: str, payload: dict) -> str:
    """Deterministic JSON of an event. Stable across a database round trip."""
    return json.dumps({"ts": ts, "action": action, "actor": actor,
                       "payload": payload},
                      sort_keys=True, separators=(",", ":"), default=str)


def append(session: Session, *, action: str, actor: str,
           payload: dict[str, Any], ts: datetime | None = None) -> KeyLifecycleEvent:
    """Chain one event onto the stream. The caller owns the transaction."""
    session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _LOCK_KEY})
    # JSON-native before hashing: what is hashed must be exactly what JSONB
    # hands back, or an honest chain fails verification on a UUID or a datetime.
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


def verify_chain(session: Session) -> tuple[bool, int | None]:
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


def as_dict(ev: KeyLifecycleEvent) -> dict[str, Any]:
    """The same shape the JSONL driver produced, so readers stay uniform."""
    return {"ts": _iso(ev.ts), "stage": STREAM,
            "action": ev.action, **ev.payload, "actor": ev.actor}


class PostgresKeyLifecycleAudit:
    """`KeyLifecycleAudit` backed by `key_lifecycle_events`, bound to a session."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def _event(self, action: str, actor: str, **payload: Any) -> None:
        append(self._session, action=action, actor=actor, payload=payload)

    def rotation(self, *, old_key_id, new_key_id, entries_reencrypted, actor,
                 scope=None) -> None:
        self._event(ROTATION_ACTION, actor, old_key_id=old_key_id, scope=scope,
                    new_key_id=new_key_id, entries_reencrypted=entries_reencrypted)

    def grant_issued(self, *, grant_id, recipient, allowed_types, document_id,
                     actor, domain=None, role=None) -> None:
        self._event(GRANT_ISSUED_ACTION, actor, grant_id=grant_id,
                    recipient=recipient, allowed_types=list(allowed_types),
                    document_id=document_id, domain=domain, role=role)

    def grant_revoked(self, *, grant_id, actor) -> None:
        self._event(GRANT_REVOKED_ACTION, actor, grant_id=grant_id)

    def role_changed(self, *, role, change, allowed_types, active, actor,
                     reason=None) -> None:
        self._event(ROLE_ACTION, actor, role=role, change=change,
                    allowed_types=list(allowed_types), active=active, reason=reason)

    def dossier_renamed(self, *, dossier_id, old, new, documents, actor) -> None:
        self._event(DOSSIER_RENAMED_ACTION, actor, dossier_id=dossier_id,
                    old=old, new=new, documents=documents)

    def events(self) -> list[dict[str, Any]]:
        return [as_dict(ev) for ev in self._session.execute(
            select(KeyLifecycleEvent).order_by(KeyLifecycleEvent.seq)).scalars()]


def export_jsonl(session: Session, *, after_seq: int = 0) -> str:
    """The stream as JSONL, one event per line, in `seq` order.

    With the table as the source of truth, the canonical form is its rows
    serialised one way — the same shape `audit.export_jsonl` gives the document
    chain. Chain fields ride along, so an exported file can be verified without
    the database.
    """
    lines = []
    for ev in session.execute(select(KeyLifecycleEvent)
                              .where(KeyLifecycleEvent.seq > after_seq)
                              .order_by(KeyLifecycleEvent.seq)).scalars():
        lines.append(json.dumps({"seq": ev.seq, **as_dict(ev),
                                 "prev_hash": ev.prev_hash, "hash": ev.hash},
                                sort_keys=True, default=str))
    return "".join(line + "\n" for line in lines)


def hash_before(session: Session, seq: int) -> str:
    """The hash an event after ``seq`` chains onto: the last one at or before it."""
    return session.execute(select(KeyLifecycleEvent.hash)
                           .where(KeyLifecycleEvent.seq <= seq)
                           .order_by(KeyLifecycleEvent.seq.desc())
                           .limit(1)).scalar_one_or_none() or GENESIS_HASH


def verify_jsonl(jsonl: str, *, prev_hash: str = GENESIS_HASH) -> tuple[bool, int | None]:
    """(ok, first_bad_seq) for an exported slice, without the database.

    ``prev_hash`` is the hash the slice chains onto; genesis for a full export.
    """
    prev = prev_hash
    for line in jsonl.splitlines():
        row = json.loads(line)
        payload = {k: v for k, v in row.items() if k not in _ENVELOPE}
        want = compute_hash(prev, _content(ts=row["ts"], action=row["action"],
                                           actor=row["actor"], payload=payload))
        if row["prev_hash"] != prev or row["hash"] != want:
            return False, row["seq"]
        prev = row["hash"]
    return True, None
