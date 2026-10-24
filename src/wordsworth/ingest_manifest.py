"""Manifest-driven corpus ingest: the provable path (pilot-ingest-manifest).

One shared record per file (`file`, `url`, `fetched_at`, `sha256`, `bytes`,
`status`, `ok`); checks run before any file is ingested; after each ingest
the `register` audit record is read back against the manifest.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .db import make_engine, make_session_factory
from .embedder import OllamaEmbedder
from .models import AuditRecord, Document
from .object_store import S3ObjectStore
from .openanonymiser_driver import OpenAnonymiserAnonymizer
from .opensearch_index import OpenSearchIndex
from .pipeline import dossiers_of, ingest, process
from .provenance import ProvenanceError, parse_fetched_at, validate_source_url
from .recovery import recover
from .states import State

MANIFEST_FIELDS = ("file", "url", "fetched_at", "sha256", "bytes", "status", "ok")
REPORT_FIELDS = ("who", "when", "robots_txt", "terms", "anubis_status", "decision")


class ManifestError(ValueError):
    """A pre-ingest check failed (manifest, corpus, or pilot report)."""


@dataclass(frozen=True)
class ManifestEntry:
    file: str
    url: str
    fetched_at: datetime
    sha256: str
    bytes: int
    status: str
    ok: bool


def manifest_record(*, file: str, url: str, fetched_at: datetime, sha256: str,
                    bytes_: int, status: str, ok: bool) -> dict:
    """The shared record as a dict -- the one format every fetcher writes
    through, even one that adds its own extra fields on top."""
    return {"file": file, "url": url, "fetched_at": fetched_at.isoformat(),
            "sha256": sha256, "bytes": bytes_, "status": status, "ok": ok}


def write_manifest_record(fp, **kwargs: Any) -> None:
    """Append one shared-format record as its own manifest line."""
    fp.write(json.dumps(manifest_record(**kwargs)) + "\n")
    fp.flush()


def read_manifest(path: Path) -> dict[str, ManifestEntry]:
    """Every record, keyed by file name. Not read partially: the first bad line aborts, naming it."""
    entries: dict[str, ManifestEntry] = {}
    for lineno, line in enumerate(path.read_text().splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            raw: dict[str, Any] = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ManifestError(f"manifest line {lineno}: invalid JSON: {exc}") from exc
        missing = [f for f in MANIFEST_FIELDS if f not in raw]
        if missing:
            raise ManifestError(
                f"manifest line {lineno} ({raw.get('file', '?')}): "
                f"missing {', '.join(missing)}")
        try:
            fetched_at = parse_fetched_at(raw["fetched_at"])
            validate_source_url(raw["url"])
        except ProvenanceError as exc:
            raise ManifestError(f"manifest line {lineno} ({raw['file']}): {exc}") from exc
        entries[raw["file"]] = ManifestEntry(
            file=raw["file"], url=raw["url"], fetched_at=fetched_at,
            sha256=raw["sha256"], bytes=raw["bytes"], status=raw["status"],
            ok=raw["ok"])
    return entries


def check_backend_env() -> None:
    """Homelab only: required, never defaulted, never inferred from URLs/hosts."""
    value = settings.backend_env
    if value != "homelab":
        raise ManifestError(
            f"WORDSWORTH_BACKEND_ENV must be 'homelab', not {value!r}")


def check_pilot_report(path: Path) -> None:
    """Refuse a run whose pilot report has no completed check (who, when,
    quoted robots.txt/terms, Anubis status) with decision 'proceed'."""
    if not path.is_file():
        raise ManifestError(f"pilot report not found: {path}")
    try:
        report = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ManifestError(f"pilot report is not valid JSON: {path}") from exc
    missing = [f for f in REPORT_FIELDS if not report.get(f)]
    if missing:
        raise ManifestError(
            f"pilot report has no completed check: missing {', '.join(missing)}")
    if report["decision"] != "proceed":
        raise ManifestError(
            f"pilot report decision is {report['decision']!r}, not 'proceed'")


def check_corpus_against_manifest(corpus_dir: Path, manifest: dict[str, ManifestEntry]) -> None:
    """Every ``*.pdf`` needs an entry (unlisted aborts the run) and its bytes must hash to it."""
    for pdf in sorted(corpus_dir.glob("*.pdf")):
        entry = manifest.get(pdf.name)
        if entry is None:
            raise ManifestError(f"{pdf.name}: no manifest entry")
        digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
        if digest != entry.sha256:
            raise ManifestError(
                f"{pdf.name}: sha256 mismatch (file {digest}, manifest {entry.sha256})")

def _advance(session: Session, store, doc: Document, anonymizer, index, embedder) -> State:
    """Drive one document to a terminal state, resuming through OCR recovery."""
    state = process(session, doc.id, store, anonymizer=anonymizer,
                    search_index=index, embedder=embedder)
    session.commit()
    if state == State.UNPROCESSABLE_OCR:
        state = recover(session, doc.id, store)
        session.commit()
        if state == State.SUPERSEDED:
            owner = session.get(Document, doc.id).superseded_by
            index.set_dossiers(str(owner), dossiers_of(session, owner))
        else:
            state = process(session, doc.id, store, anonymizer=anonymizer,
                            search_index=index, embedder=embedder)
            session.commit()
    return state

def _verify_provenance(session: Session, document_id: UUID, entry: ManifestEntry) -> str | None:
    """None when the ``register`` record matches the manifest; else the reason."""
    payload = session.execute(
        select(AuditRecord.payload)
        .where(AuditRecord.document_id == document_id, AuditRecord.step == "register")
        .order_by(AuditRecord.seq).limit(1)
    ).scalar_one_or_none() or {}
    source_url, fetched_at = payload.get("source_url"), payload.get("fetched_at")
    if source_url != entry.url:
        return f"source_url differs: recorded {source_url!r}, manifest {entry.url!r}"
    if fetched_at != entry.fetched_at.isoformat():
        return (f"fetched_at differs: recorded {fetched_at!r}, "
                f"manifest {entry.fetched_at.isoformat()!r}")
    return None

def ingest_manifest_corpus(corpus_dir: Path, dossier: str, manifest_path: Path,
                           pilot_report: Path) -> list[tuple[str, str]]:
    """Ingest every ``*.pdf`` in ``corpus_dir`` against ``manifest_path``.
    Returns ``(filename, outcome)`` per file: a terminal state name, or
    ``"failed: <reason>"``. Every check above runs before any backend is touched."""
    check_backend_env()
    check_pilot_report(pilot_report)
    manifest = read_manifest(manifest_path)
    check_corpus_against_manifest(corpus_dir, manifest)

    engine = make_engine()
    session_factory = make_session_factory(engine)
    store = S3ObjectStore.from_config()
    anonymizer = OpenAnonymiserAnonymizer()
    index = OpenSearchIndex.from_config()
    embedder = OllamaEmbedder.from_config()
    index.ensure_ready()

    results: list[tuple[str, str]] = []
    def record(name: str, outcome: str) -> None:
        results.append((name, outcome))
        print(f"{name}: {outcome}")

    for pdf in sorted(corpus_dir.glob("*.pdf")):
        entry = manifest[pdf.name]
        with session_factory() as session:
            doc = ingest(session, store, pdf.read_bytes(), filename=pdf.name,
                        dossier=dossier, source_url=entry.url,
                        fetched_at=entry.fetched_at)
            session.commit()
            try:
                state = _advance(session, store, doc, anonymizer, index, embedder)
            except Exception as exc:  # a layer that did not run fails the run
                record(pdf.name, f"failed: layer error ({exc})")
                continue
            reason = _verify_provenance(session, doc.id, entry)
            record(pdf.name, f"failed: {reason}" if reason else state.value)
    return results
