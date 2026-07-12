"""WORM export of the hash-chained audit trail to S3 Object Lock storage.

Writes the derived JSONL (from ``audit.export_jsonl``) to an object store that
holds each object write-once under a retention lock, so the exported chain
cannot be altered or deleted for the bewaartermijn. Two layers of tamper-
evidence: the hash chain makes alteration *detectable*, Object Lock makes it
*impossible* until expiry. Every export re-verifies against PostgreSQL first; a
non-verifying or partial export is a hard failure, never a silent partial.

Object Lock/WORM is the audit export's own concern (see the object-storage
design): the base ObjectStore only stores bytes, so this module defines the
retention-aware seam. ``S3WormStore`` is the driver (a boto3-style client is
injected — creds come from object-storage's secret source, never hardcoded);
``InMemoryWormStore`` is the test double enforcing write-once semantics."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol, runtime_checkable

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import audit
from .hashing import GENESIS_HASH, canonical_content, compute_hash
from .models import AuditRecord


class ExportError(RuntimeError):
    """An export that did not verify. Never downgraded to a partial success."""


class WormRetentionError(RuntimeError):
    """Raised when a retention-locked object is overwritten or deleted."""


@runtime_checkable
class WormObjectStore(Protocol):
    """Object store with S3 Object Lock (compliance-mode) semantics."""

    def put_object_locked(
        self, key: str, data: bytes, retain_until: datetime
    ) -> None: ...
    def get(self, key: str) -> bytes: ...
    def retain_until(self, key: str) -> datetime | None: ...


@dataclass
class InMemoryWormStore:
    """Dict-backed double enforcing write-once until ``retain_until``.

    ``now`` defaults to the wall clock; tests inject a fixed value to prove the
    lock holds (and, by advancing it, that it releases only after expiry)."""

    now: datetime | None = None
    _objects: dict[str, tuple[bytes, datetime]] = field(default_factory=dict)

    def _clock(self) -> datetime:
        return self.now or datetime.now(timezone.utc)

    def _guard(self, key: str) -> None:
        existing = self._objects.get(key)
        if existing is not None and self._clock() < existing[1]:
            raise WormRetentionError(f"{key} is retention-locked until {existing[1]}")

    def put_object_locked(self, key, data, retain_until) -> None:
        self._guard(key)
        self._objects[key] = (data, retain_until)

    def delete(self, key: str) -> None:
        self._guard(key)
        self._objects.pop(key, None)

    def get(self, key: str) -> bytes:
        return self._objects[key][0]

    def retain_until(self, key: str) -> datetime | None:
        obj = self._objects.get(key)
        return obj[1] if obj else None


@dataclass
class S3WormStore:
    """S3 Object Lock driver. ``client`` is an injected boto3-style S3 client
    (endpoint/creds sourced by object-storage from SOPS+age or OpenBao)."""

    client: Any
    bucket: str

    def put_object_locked(self, key, data, retain_until) -> None:
        self.client.put_object(
            Bucket=self.bucket, Key=key, Body=data,
            ObjectLockMode="COMPLIANCE", ObjectLockRetainUntilDate=retain_until,
        )

    def get(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def retain_until(self, key: str) -> datetime | None:
        head = self.client.head_object(Bucket=self.bucket, Key=key)
        return head.get("ObjectLockRetainUntilDate")


@dataclass
class ExportResult:
    object_key: str | None
    first_seq: int | None
    last_seq: int
    count: int
    retain_until: datetime | None


def _hash_at(session: Session, seq: int) -> str | None:
    return session.execute(
        select(AuditRecord.hash).where(AuditRecord.seq == seq)
    ).scalar_one_or_none()


def verify_export(session: Session, jsonl_text: str, *, after_seq: int = 0) -> bool:
    """Re-verify exported JSONL against the database.

    Confirms line count, per-record linkage and hash recompute, and that every
    exported field matches the PostgreSQL source. A tampered or partial export
    fails here."""
    lines = jsonl_text.splitlines() if jsonl_text else []
    records = session.execute(
        select(AuditRecord).where(AuditRecord.seq > after_seq).order_by(AuditRecord.seq)
    ).scalars().all()
    if len(lines) != len(records):
        return False
    prev = GENESIS_HASH
    if after_seq:
        prev = _hash_at(session, after_seq)
        if prev is None:
            return False
    for line, rec in zip(lines, records):
        data = json.loads(line)
        # Matches the PostgreSQL source: seq and hashes equal the DB row.
        if data.get("seq") != rec.seq or data.get("hash") != rec.hash:
            return False
        if data.get("prev_hash") != rec.prev_hash or data.get("prev_hash") != prev:
            return False
        # Links correctly: recompute from the exported line's OWN content, so an
        # altered field with a stale hash is caught (not trusted against the DB).
        try:
            content = canonical_content(
                document_id=data["document_id"], from_state=data["from_state"],
                to_state=data["to_state"], ts=datetime.fromisoformat(data["ts"]),
                step=data["step"], payload=data["payload"],
            )
        except (KeyError, ValueError):
            return False
        if compute_hash(data["prev_hash"], content) != data["hash"]:
            return False
        prev = data["hash"]
    return True


def _last_seq(session: Session) -> int:
    return session.execute(
        select(AuditRecord.seq).order_by(AuditRecord.seq.desc()).limit(1)
    ).scalar_one_or_none() or 0


def export_worm(
    session: Session,
    store: WormObjectStore,
    *,
    retention_days: int,
    after_seq: int = 0,
    now: datetime | None = None,
    key_prefix: str = "audit-chain",
) -> ExportResult:
    """Export records after ``after_seq`` to a retention-locked object.

    ``retention_days`` is the bewaartermijn for this export (callers pass the
    term for the relevant category). Verifies the DB chain, then the generated
    slice, then the bytes read back from the store; any failure raises
    ``ExportError`` rather than reporting a partial success."""
    ok, bad = audit.verify_chain(session)
    if not ok:
        raise ExportError(f"database chain does not verify at seq {bad}")
    last = _last_seq(session)
    if last <= after_seq:
        return ExportResult(None, None, after_seq, 0, None)
    jsonl = audit.export_jsonl(session, after_seq=after_seq)
    if not verify_export(session, jsonl, after_seq=after_seq):
        raise ExportError("exported slice does not verify against the database")
    first_seq = after_seq + 1
    key = f"{key_prefix}/seq-{first_seq:012d}-{last:012d}.jsonl"
    now = now or datetime.now(timezone.utc)
    retain_until = now + timedelta(days=retention_days)
    store.put_object_locked(key, jsonl.encode("utf-8"), retain_until)
    stored = store.get(key).decode("utf-8")
    if stored != jsonl or not verify_export(session, stored, after_seq=after_seq):
        raise ExportError("stored object does not verify against the database")

    return ExportResult(key, first_seq, last, last - after_seq, retain_until)
