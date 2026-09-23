"""WORM export of the key-lifecycle stream.

Gap 28 in the NORA analysis. ``audit_export.export_worm`` exports the *document*
chain; this exports the key-lifecycle stream (``key_audit_pg.py``), the one that
answers "who issued, revoked or rotated what, and when" — the question that
arrives *after* an incident, when the host that holds the stream is itself
suspect.

Own module because ``audit_export.py`` sits at the 200-line limit; the retention
semantics and the store protocol are imported from there so there is one
definition of what WORM means here.

**Two layers of tamper-evidence since key-audit-in-postgres (2026-09-23).**
Before that change the stream was an unchained JSONL file, and this function
exported whatever the file said: Object Lock protected what was exported, not
what was written. The stream is now a hash-chained table, so the export does
what the document export does: verify the chain in the database, export in
``seq`` order, and check the stored bytes against the database before reporting
success.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from . import key_audit_pg
from .audit_export import ExportError, ExportResult, WormObjectStore


def export_key_lifecycle_worm(
    session: Session,
    store: WormObjectStore,
    *,
    retention_days: int,
    after_seq: int = 0,
    now: datetime | None = None,
    key_prefix: str = "key-lifecycle",
) -> ExportResult:
    """Export events after ``after_seq`` to a retention-locked object.

    Incremental like the document export: pass the previous result's
    ``last_seq`` and a scheduled run ships only what is new. Nothing to export
    is not an error — it is a stream that stood still.

    ``seq`` has gaps: an event rolled back with its change still consumed a
    number. So first, last and count come from the exported rows, never from
    subtracting sequence numbers.
    """
    ok, bad = key_audit_pg.verify_chain(session)
    if not ok:
        raise ExportError(f"key-lifecycle chain does not verify at seq {bad}")
    jsonl = key_audit_pg.export_jsonl(session, after_seq=after_seq)
    if not jsonl:
        return ExportResult(None, None, after_seq, 0, None)

    seqs = [json.loads(line)["seq"] for line in jsonl.splitlines()]
    first, last = seqs[0], seqs[-1]
    key = f"{key_prefix}/seq-{first:012d}-{last:012d}.jsonl"
    now = now or datetime.now(timezone.utc)
    retain_until = now + timedelta(days=retention_days)

    store.put_object_locked(key, jsonl.encode("utf-8"), retain_until)
    stored = store.get(key).decode("utf-8")
    prev = key_audit_pg.hash_before(session, after_seq)
    if stored != jsonl or not key_audit_pg.verify_jsonl(stored, prev_hash=prev)[0]:
        raise ExportError(f"stored object {key} does not match the database")

    return ExportResult(key, first, last, len(seqs), retain_until)
