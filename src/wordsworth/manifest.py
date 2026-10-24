# SPDX-License-Identifier: MIT
"""The shared per-file manifest record (pilot-ingest-manifest).

One format for every fetcher, scripted or by hand, and for
`wordsworth-ingest --manifest`: ``file``, ``url``, ``fetched_at`` (ISO-8601
with a timezone, the real download time), ``sha256``, ``bytes``, ``status``
and ``ok``. A mix-up between a manifest and the files it describes then fails
loudly instead of each fetcher inventing its own vocabulary that ingest has to
special-case.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

FIELDS = ("file", "url", "fetched_at", "sha256", "bytes", "status", "ok")


class ManifestError(ValueError):
    """A malformed manifest line, naming the file and the line number."""


@dataclass(frozen=True)
class ManifestEntry:
    file: str
    url: str
    fetched_at: str  # ISO-8601 with a timezone; parsed by the caller
    sha256: str
    bytes: int
    status: str
    ok: bool


def write_entry(fh: TextIO, entry: ManifestEntry) -> None:
    """Append one record, the way every fetcher writes it. Flushed immediately
    so a crashed fetch leaves a manifest that matches the files it did write,
    not one short a trailing buffered line."""
    fh.write(json.dumps({f: getattr(entry, f) for f in FIELDS}) + "\n")
    fh.flush()


def read_manifest(path: Path) -> dict[str, ManifestEntry]:
    """Every entry, keyed by `file`. A line missing a required field is a hard
    error naming the file and the line; a later line for the same `file`
    overwrites an earlier one (a manifest is written with ``append``, so
    re-running a fetch duplicates lines -- harmless here for the same reason it
    is harmless to `wordsworth-dossier-uit-herkomst`)."""
    entries: dict[str, ManifestEntry] = {}
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ManifestError(f"{path}:{lineno}: not valid JSON") from exc
        missing = [f for f in FIELDS if f not in row]
        if missing:
            raise ManifestError(
                f"{path}:{lineno}: missing {', '.join(missing)}")
        entries[row["file"]] = ManifestEntry(**{f: row[f] for f in FIELDS})
    return entries
