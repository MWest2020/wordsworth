"""WORM export of the key-lifecycle stream.

Gap 28 in the NORA analysis, and the last real one. ``audit_export.export_worm``
exports the *document* chain; the key-lifecycle stream (``key_audit.py``) stayed
append-only JSONL on disk and never reached Object Lock. That is the stream that
answers "who rotated which key, and when" — the question that arrives *after* an
incident, when the host holding that file is itself suspect.

Own module because ``audit_export.py`` sits at the 200-line limit; the retention
semantics and the store protocol are imported from there so there is one
definition of what WORM means here.

**One layer of tamper-evidence, not two, and that is worth saying out loud.**
The document chain is hash-chained *and* Object-Locked: alteration is detectable
in the database and impossible in the store. The key-lifecycle stream is
append-only but not chained, so a host compromised *before* an export could
rewrite the JSONL and this function would faithfully export the rewritten
version. Object Lock protects what was exported, not what was written. Chaining
this stream is a separate change (``harden-key-audit-chain``) and deliberately
not smuggled in here.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol, runtime_checkable

from .audit_export import ExportError, ExportResult, WormObjectStore


@runtime_checkable
class KeyLifecycleStream(Protocol):
    """What this export needs: the file the stream is written to.

    Bytes, not parsed events. An export that re-serialises would produce a file
    that *means* the same and *is* different, and then "does the export match
    the source" stops being a question you can answer with a comparison.
    """

    path: Path


def _lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return [ln for ln in fh.read().splitlines() if ln.strip()]


def export_key_lifecycle_worm(
    stream: KeyLifecycleStream,
    store: WormObjectStore,
    *,
    retention_days: int,
    after_line: int = 0,
    now: datetime | None = None,
    key_prefix: str = "key-lifecycle",
) -> ExportResult:
    """Export events after ``after_line`` to a retention-locked object.

    Incremental like the document export: ``after_line`` is the count already
    exported, so a scheduled run ships only what is new. Nothing to export is
    not an error — it is a stream that stood still.

    Verifies the bytes read back from the store against what was sent; a
    mismatch raises ``ExportError`` rather than reporting a partial success.
    """
    regels = _lines(Path(stream.path))
    if len(regels) <= after_line:
        return ExportResult(None, None, after_line, 0, None)

    plak = regels[after_line:]
    jsonl = "\n".join(plak) + "\n"
    eerste, laatste = after_line + 1, len(regels)
    key = f"{key_prefix}/line-{eerste:012d}-{laatste:012d}.jsonl"
    now = now or datetime.now(timezone.utc)
    retain_until = now + timedelta(days=retention_days)

    store.put_object_locked(key, jsonl.encode("utf-8"), retain_until)
    opgeslagen = store.get(key).decode("utf-8")
    if opgeslagen != jsonl:
        raise ExportError(
            f"stored object {key} does not match the exported slice "
            f"({len(opgeslagen)} vs {len(jsonl)} bytes)")

    return ExportResult(key, eerste, laatste, len(plak), retain_until)
