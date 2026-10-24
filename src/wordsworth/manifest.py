"""The shared manifest record (pilot-ingest-manifest): one format for every
fetcher, read by ``ingest_manifest.py``.

A scripted fetch and a person fetching by hand write the same record — ``file``
(the name the PDF was saved under), ``url``, ``fetched_at`` (ISO-8601 with a
timezone, the real download time), ``sha256``, ``bytes``, ``status`` and
``ok``. A mix-up between a manifest and the files it describes then fails
loudly at ingest, instead of silently.

Extra, fetcher-specific keys on a line (e.g. ``besluit``, the Woo decision page
a file came from) are preserved by :func:`write_record` and ignored by
:func:`read_manifest` — this format is additive, not exclusive.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any

#: Fields every manifest entry must carry; see the module docstring.
REQUIRED_FIELDS = ("file", "url", "fetched_at", "sha256", "bytes", "status", "ok")


class ManifestError(ValueError):
    """A manifest file is missing, malformed, or missing a required field."""


@dataclass(frozen=True)
class ManifestEntry:
    file: str
    url: str
    fetched_at: str  # ISO-8601 with a timezone, exactly as the fetcher wrote it
    sha256: str
    bytes: int
    status: str
    ok: bool


def write_record(fh: IO[str], *, file: str, url: str, fetched_at: str,
                  sha256: str, bytes: int, status: str, ok: bool,
                  **extra: Any) -> None:
    """Append one record, flushed immediately — the same shape a crash-prone
    long-running fetch needs: every file downloaded so far stays recorded even
    if the next one fails. ``extra`` keys (a fetcher's own bookkeeping) ride
    along unexamined."""
    record: dict[str, Any] = {
        "file": file, "url": url, "fetched_at": fetched_at, "sha256": sha256,
        "bytes": bytes, "status": status, "ok": ok,
    }
    record.update(extra)
    fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    fh.flush()


def _entry_from(raw: dict, *, line_no: int, path: Path) -> ManifestEntry:
    missing = [f for f in REQUIRED_FIELDS if f not in raw]
    if missing:
        raise ManifestError(
            f"{path}:{line_no}: missing field(s) {', '.join(missing)}"
        )
    return ManifestEntry(
        file=str(raw["file"]), url=str(raw["url"]),
        fetched_at=str(raw["fetched_at"]), sha256=str(raw["sha256"]),
        bytes=int(raw["bytes"]), status=str(raw["status"]), ok=bool(raw["ok"]),
    )


def read_manifest(path: Path) -> dict[str, ManifestEntry]:
    """Every entry, keyed by ``file``. A later line for the same file wins —
    the same tolerance `dossier_tools` already gives a fetcher's append-only
    log (a rerun duplicates lines, harmlessly)."""
    if not path.is_file():
        raise ManifestError(f"manifest not found: {path}")
    entries: dict[str, ManifestEntry] = {}
    with path.open(encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ManifestError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
            entry = _entry_from(raw, line_no=line_no, path=path)
            entries[entry.file] = entry
    return entries
