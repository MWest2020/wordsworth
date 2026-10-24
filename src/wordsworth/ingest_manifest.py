"""Manifest-driven corpus ingest (pilot-ingest-manifest): the same straat as
``ingest_corpus.py``, with provenance proved rather than merely passed along.

Checks run before any file is ingested, in this order: the backend is
homelab, the pilot report holds a completed check, every ``*.pdf`` in the
corpus directory has a manifest entry, and every file's sha256 matches it.
Only then does ingestion start. After each document, its ``register`` audit
record is read back and compared with the manifest — this is the proof, not a
re-run of the logic that wrote it (AGENTS.md: "measure the artefact").

A document that does not reach ``indexed`` — including because OpenAnonymiser
was down — is a failure, not a success with a note. Not changed here: what
``ingest()`` does with a duplicate. A pilot PDF already live as a document
(this dossier or another) keeps its first provenance and fails the read-back.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from .config import settings
from .db import make_engine, make_session_factory
from .embedder import OllamaEmbedder
from .manifest import ManifestEntry, ManifestError, read_manifest
from .models import AuditRecord, Document
from .object_store import S3ObjectStore
from .openanonymiser_driver import OpenAnonymiserAnonymizer
from .opensearch_index import OpenSearchIndex
from .pipeline import dossiers_of, ingest, process
from .recovery import recover
from .states import State

#: Fields a pilot report must carry, non-empty, before a manifest run is
#: allowed to start (design.md: "who, when, quoted robots.txt and terms,
#: Anubis status, decision"). The path and the report's authoring step belong
#: to `pilot-report-template`; this only validates what is handed to it.
_REQUIRED_REPORT_FIELDS = ("who", "when", "robots", "terms", "anubis", "decision")


@dataclass(frozen=True)
class ManifestResult:
    filename: str
    ok: bool
    state: State | None
    reason: str | None = None


def _check_backend() -> None:
    if settings.backend_env != "homelab":
        got = settings.backend_env or "(unset)"
        raise ManifestError(
            f"WORDSWORTH_BACKEND_ENV must be 'homelab' for a manifest run, got {got!r}"
        )


def _check_pilot_report(path: Path) -> dict:
    if not path.is_file():
        raise ManifestError(f"pilot report not found: {path}")
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestError(f"pilot report is not valid JSON: {exc}") from exc
    missing = [f for f in _REQUIRED_REPORT_FIELDS if not str(report.get(f, "")).strip()]
    if missing:
        raise ManifestError(
            f"pilot report has no completed check: missing {', '.join(missing)}"
        )
    if report["decision"] != "proceed":
        raise ManifestError(
            f"pilot report decision is {report['decision']!r}, not 'proceed'"
        )
    return report


def _check_files(corpus_dir: Path, manifest: dict[str, ManifestEntry]) -> list[Path]:
    """Every ``*.pdf`` has an entry and its sha256 matches it. Returns the PDFs
    in ingest order. Raises naming every problem at once — this is a single
    abort, not a skip per file."""
    pdfs = sorted(corpus_dir.glob("*.pdf"))
    problems: list[str] = []
    for pdf in pdfs:
        entry = manifest.get(pdf.name)
        if entry is None:
            problems.append(f"{pdf.name}: not in the manifest")
            continue
        digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
        if digest != entry.sha256:
            problems.append(
                f"{pdf.name}: sha256 mismatch (file {digest}, manifest {entry.sha256})"
            )
    if problems:
        raise ManifestError("manifest check failed:\n  " + "\n  ".join(problems))
    return pdfs


def _advance(session, document_id: UUID, store, anonymizer, index, embedder) -> State:
    state = process(session, document_id, store, anonymizer=anonymizer,
                     search_index=index, embedder=embedder)
    if state == State.UNPROCESSABLE_OCR:
        state = recover(session, document_id, store)
        if state == State.SUPERSEDED:
            owner = session.get(Document, document_id).superseded_by
            index.set_dossiers(str(owner), dossiers_of(session, owner))
        else:
            state = process(session, document_id, store, anonymizer=anonymizer,
                             search_index=index, embedder=embedder)
    return state


def _register_payload(session, document_id: UUID) -> dict:
    return session.execute(
        select(AuditRecord.payload)
        .where(AuditRecord.document_id == document_id, AuditRecord.step == "register")
        .order_by(AuditRecord.seq)
        .limit(1)
    ).scalar_one_or_none() or {}


def _check_provenance(session, document_id: UUID, entry: ManifestEntry,
                       fetched_at: datetime) -> str | None:
    """None when the ``register`` record carries this manifest's provenance;
    otherwise the reason it does not — e.g. these bytes were already a
    document, with no or other provenance (the duplicate-key case: `ingest()`
    is left alone, so this read-back is the only place that catches it)."""
    payload = _register_payload(session, document_id)
    if payload.get("source_url") != entry.url:
        return f"register source_url {payload.get('source_url')!r} != manifest {entry.url!r}"
    if payload.get("fetched_at") != fetched_at.isoformat():
        return (f"register fetched_at {payload.get('fetched_at')!r} != "
                f"manifest {fetched_at.isoformat()!r}")
    return None


def ingest_manifest_corpus(corpus_dir: Path, dossier: str, manifest_path: Path,
                           pilot_report_path: Path, *, session_factory=None,
                           store=None, anonymizer=None, index=None,
                           embedder=None) -> list[ManifestResult]:
    """Backends default to the real sovereign ones (as ``ingest_corpus`` does);
    tests inject fakes (``mem_store``, ``mem_index``, ``fake_embedder``, a
    double ``Anonymizer``) the same way ``pipeline.process`` already lets
    them, so this straat is exercised end to end without live services."""
    _check_backend()
    _check_pilot_report(pilot_report_path)
    manifest = read_manifest(manifest_path)
    pdfs = _check_files(corpus_dir, manifest)

    session_factory = session_factory or make_session_factory(make_engine())
    store = store or S3ObjectStore.from_config()
    anonymizer = anonymizer or OpenAnonymiserAnonymizer()
    index = index or OpenSearchIndex.from_config()
    embedder = embedder or OllamaEmbedder.from_config()
    index.ensure_ready()

    results: list[ManifestResult] = []
    for pdf in pdfs:
        entry = manifest[pdf.name]
        fetched_at = datetime.fromisoformat(entry.fetched_at)
        with session_factory() as session:
            try:
                doc = ingest(session, store, pdf.read_bytes(), filename=pdf.name,
                             dossier=dossier, source_url=entry.url, fetched_at=fetched_at)
                session.commit()
                state = _advance(session, doc.id, store, anonymizer, index, embedder)
                session.commit()
            except Exception as exc:
                session.rollback()
                reason = f"{type(exc).__name__}: processing failed before completion"
                results.append(ManifestResult(pdf.name, ok=False, state=None, reason=reason))
                print(f"{pdf.name}: FAILED ({reason})")
                continue

            reason = _check_provenance(session, doc.id, entry, fetched_at)
            if reason is None and state != State.INDEXED:
                reason = f"did not reach indexed (state={state.value})"
            ok = reason is None
            results.append(ManifestResult(pdf.name, ok=ok, state=state, reason=reason))
            print(f"{pdf.name}: {state.value}" + ("" if ok else f" FAILED ({reason})"))
    return results
