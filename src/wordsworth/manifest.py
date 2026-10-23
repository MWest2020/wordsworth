"""Shared ingest manifest: one JSONL record per file, written by every
fetcher and read by `ingest_corpus.py --manifest` (pilot-ingest-manifest).

``bestand`` is the file-identifying key -- the name `fetch_woo_corpus.py` and
`dossier_tools.by_filename` already read and write. Renaming it to something
like `filename` would silently break both the moment a fetcher "moves to the
shared format"; see design.md's "Settled". `url` and `fetched_at` reuse the
ingest-records-source vocabulary already on `Document`. Extra per-fetcher
fields (`besluit`, `bytes`) are accepted and ignored -- one shared format does
not mean every fetcher carries nothing else.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .provenance import ProvenanceError, parse_fetched_at, validate_source_url


class ManifestError(ValueError):
    """A manifest is malformed, or a corpus file has no entry or a wrong
    hash. The message names the file; the run that raises this refuses
    before any file is ingested, never skips the file quietly."""


@dataclass(frozen=True)
class ManifestEntry:
    filename: str
    url: str
    fetched_at: datetime
    sha256: str


def read_manifest(path: Path) -> dict[str, ManifestEntry]:
    """Parse a JSONL manifest into ``{bestand: ManifestEntry}``.

    Each line must carry ``bestand``, ``url``, ``fetched_at`` (ISO-8601 with a
    timezone) and ``sha256``; other fields are ignored. A malformed line fails
    loudly, naming the line -- a manifest half-trusted is worse than one
    refused outright."""
    entries: dict[str, ManifestEntry] = {}
    for lineno, raw_line in enumerate(path.read_text().splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ManifestError(f"manifest line {lineno} is not valid JSON") from exc
        try:
            filename = row["bestand"]
            url = validate_source_url(row["url"])
            fetched_at = parse_fetched_at(row["fetched_at"])
            sha256 = str(row["sha256"]).lower()
        except KeyError as exc:
            raise ManifestError(
                f"manifest line {lineno} has no {exc.args[0]!r}") from exc
        except ProvenanceError as exc:
            raise ManifestError(f"manifest line {lineno}: {exc}") from exc
        entries[filename] = ManifestEntry(filename, url, fetched_at, sha256)
    return entries


def append_entry(path: Path, *, filename: str, url: str, fetched_at: datetime,
                 sha256: str, extra: dict | None = None) -> None:
    """Append one record the way every fetcher writes the manifest: opened in
    append mode and flushed immediately, so a crash mid-fetch never loses the
    records already on disk. ``extra`` carries fetcher-specific fields
    (e.g. `besluit`, `bytes`) the shared reader tolerates but does not need."""
    record = {"bestand": filename, "url": url,
              "fetched_at": fetched_at.isoformat(), "sha256": sha256}
    record.update(extra or {})
    with path.open("a") as fp:
        fp.write(json.dumps(record) + "\n")
        fp.flush()
