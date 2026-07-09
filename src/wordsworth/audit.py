"""Append, verify, and export the global hash-chained audit trail.

Appends serialise on a transaction-scoped advisory lock so the global chain
never forks under concurrent writers; the UNIQUE(prev_hash) constraint is the
backstop. The caller owns the transaction (commit/rollback)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .hashing import GENESIS_HASH, canonical_content, compute_hash
from .models import AuditRecord

# Arbitrary constant key identifying the single global audit chain.
_CHAIN_LOCK_KEY = 4771


def _tail_hash(session: Session) -> str:
    tail = session.execute(
        select(AuditRecord.hash).order_by(AuditRecord.seq.desc()).limit(1)
    ).scalar_one_or_none()
    return tail or GENESIS_HASH


def append(
    session: Session,
    *,
    document_id: UUID,
    from_state: str | None,
    to_state: str,
    step: str,
    payload: dict[str, Any] | None = None,
    ts: datetime | None = None,
) -> AuditRecord:
    session.execute(
        text("SELECT pg_advisory_xact_lock(:k)"), {"k": _CHAIN_LOCK_KEY}
    )
    payload = payload or {}
    ts = ts or datetime.now(timezone.utc)
    prev = _tail_hash(session)
    content = canonical_content(
        document_id=document_id,
        from_state=from_state,
        to_state=to_state,
        ts=ts,
        step=step,
        payload=payload,
    )
    record = AuditRecord(
        document_id=document_id,
        from_state=from_state,
        to_state=to_state,
        ts=ts,
        step=step,
        payload=payload,
        prev_hash=prev,
        hash=compute_hash(prev, content),
    )
    session.add(record)
    session.flush()
    return record


def verify_chain(session: Session) -> tuple[bool, int | None]:
    """Return (ok, first_bad_seq). Walks the chain, recomputing every hash."""
    prev = GENESIS_HASH
    records = session.execute(
        select(AuditRecord).order_by(AuditRecord.seq)
    ).scalars().all()
    for rec in records:
        if rec.prev_hash != prev:
            return False, rec.seq
        content = canonical_content(
            document_id=rec.document_id,
            from_state=rec.from_state,
            to_state=rec.to_state,
            ts=rec.ts,
            step=rec.step,
            payload=rec.payload,
        )
        if compute_hash(rec.prev_hash, content) != rec.hash:
            return False, rec.seq
        prev = rec.hash
    return True, None


def export_jsonl(session: Session, *, after_seq: int = 0) -> str:
    """Derived, append-only JSONL view: same records, same hashes.

    ``after_seq`` yields only records past that seq, for incremental export.
    ``after_seq=0`` (the default) yields the full chain."""
    lines = []
    records = session.execute(
        select(AuditRecord)
        .where(AuditRecord.seq > after_seq)
        .order_by(AuditRecord.seq)
    ).scalars().all()
    for r in records:
        lines.append(
            json.dumps(
                {
                    "seq": r.seq,
                    "document_id": str(r.document_id),
                    "from_state": r.from_state,
                    "to_state": r.to_state,
                    "ts": r.ts.astimezone(timezone.utc).isoformat(),
                    "step": r.step,
                    "payload": r.payload,
                    "prev_hash": r.prev_hash,
                    "hash": r.hash,
                },
                sort_keys=True,
                ensure_ascii=False,
            )
        )
    return "\n".join(lines)
