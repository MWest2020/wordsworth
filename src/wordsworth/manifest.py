"""The shared manifest record: how every fetcher hands provenance to ingest.

One format -- ``file``, ``url``, ``fetched_at``, ``sha256``, ``bytes``,
``status``, ``ok`` -- written by whichever fetcher gathered a corpus (a script
or a person by hand) and read by ``ingest_corpus.py --manifest``. A mix-up
between manifest and file fails loudly (`manifest_line`/`read_manifest` are
the one pair of functions that write and read it).

The pilot's completed-check gate (``check.json``, next to the manifest) lives
here too: it is read before any manifest entry is trusted, by the same module
that defines what a line means.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .provenance import parse_fetched_at

REQUIRED_CHECK_FIELDS = (
    "checked_by", "checked_at", "robots_txt_url", "robots_txt", "paths_used",
    "paths_disallowed_used", "terms", "anubis", "user_agent", "delay_seconds",
    "decision",
)

_REQUIRED_ENTRY_FIELDS = ("file", "url", "fetched_at", "sha256", "bytes", "status", "ok")


@dataclass(frozen=True)
class ManifestEntry:
    file: str
    url: str
    fetched_at: datetime
    sha256: str
    bytes: int
    status: int
    ok: bool


class ManifestError(ValueError):
    """A manifest line is missing a required field or is malformed."""


class CheckError(ValueError):
    """``check.json`` is missing, incomplete, or names a refused decision."""


def manifest_line(*, file: str, url: str, fetched_at: str, sha256: str,
                   bytes_: int, status: int, ok: bool) -> str:
    """One shared manifest record, serialised the way every fetcher writes it.

    ``fetched_at`` is the caller's ISO-8601-with-timezone string, not a
    `datetime` -- the fetcher that calls this never needs to import
    `provenance` just to format what it already measured."""
    return json.dumps(
        {"file": file, "url": url, "fetched_at": fetched_at, "sha256": sha256,
         "bytes": bytes_, "status": status, "ok": ok},
        ensure_ascii=False,
    )


def read_manifest(path: Path) -> dict[str, ManifestEntry]:
    """``filename -> ManifestEntry`` for every line in ``path``.

    A missing required field or a malformed ``fetched_at`` fails the whole
    manifest loudly -- ingest never guesses at a record it cannot parse."""
    entries: dict[str, ManifestEntry] = {}
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ManifestError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
        missing = [f for f in _REQUIRED_ENTRY_FIELDS if f not in row]
        if missing:
            raise ManifestError(f"{path}:{lineno}: missing field(s) {missing}")
        entries[row["file"]] = ManifestEntry(
            file=row["file"], url=row["url"],
            fetched_at=parse_fetched_at(row["fetched_at"]),
            sha256=row["sha256"], bytes=row["bytes"],
            status=row["status"], ok=row["ok"],
        )
    return entries


def load_check(manifest_path: Path) -> dict:
    """Read and validate ``check.json`` next to ``manifest_path``.

    Raises `CheckError` naming the failed condition; returns the parsed
    object only when every field is present, no disallowed path was used, and
    the recorded decision is ``proceed``."""
    check_path = manifest_path.parent / "check.json"
    if not check_path.is_file():
        raise CheckError(f"check.json not found next to {manifest_path}")
    check = json.loads(check_path.read_text(encoding="utf-8"))
    missing = [f for f in REQUIRED_CHECK_FIELDS if f not in check]
    if missing:
        raise CheckError(f"check.json missing field(s): {missing}")
    if check["paths_disallowed_used"]:
        raise CheckError(
            "check.json paths_disallowed_used is not empty: "
            f"{check['paths_disallowed_used']}")
    if check["decision"] != "proceed":
        raise CheckError(f"check.json decision is {check['decision']!r}, not 'proceed'")
    return check
