# SPDX-License-Identifier: MIT
"""Manifest-driven corpus ingest (pilot-ingest-manifest).

`ingest_corpus.py --manifest` dispatches here. Every check that needs no
backend runs first: the environment names homelab, the pilot report records a
completed check, every `*.pdf` has a manifest entry and the sha256 the script
computes from the bytes agrees with it. Only then is anything ingested, and
after each ingest the `register` audit record is read back and compared with
the manifest -- the proof that provenance actually landed, not a second trust
of the same input.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .db import make_engine, make_session_factory
from .embedder import OllamaEmbedder
from .manifest import ManifestEntry, ManifestError, read_manifest
from .models import AuditRecord, Document
from .object_store import ObjectStore, S3ObjectStore
from .openanonymiser_driver import OpenAnonymiserAnonymizer
from .opensearch_index import OpenSearchIndex
from .pipeline import dossiers_of, ingest, process
from .provenance import ProvenanceError, parse_fetched_at
from .recovery import recover
from .states import State

_REQUIRED_CHECK_FIELDS = (
    "checked_by", "checked_at", "robots_txt", "terms", "anubis", "decision",
)


@dataclass(frozen=True)
class ManifestResult:
    filename: str
    ok: bool
    reason: str | None = None


def require_homelab_backend() -> None:
    """Refuse a manifest run unless `WORDSWORTH_BACKEND_ENV` is declared and is
    exactly `homelab`. Missing, empty, `alma` or anything else is refused --
    never inferred, never defaulted (a guess here is not auditable)."""
    value = settings.backend_env
    if value != "homelab":
        raise ManifestError(
            "WORDSWORTH_BACKEND_ENV must be 'homelab' for a manifest run, "
            f"not {value or '(unset)'!r}")


def require_completed_pilot_check(report_path: Path) -> None:
    """Refuse a manifest whose pilot report has no completed robots/terms/
    Anubis check (who, when, the quoted text, Anubis status) recording the
    decision `proceed`. The report's exact home and the rest of its fields are
    `pilot-report-template`'s to settle; this only enforces the gate the pilot
    plan requires before any file is touched."""
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"pilot report unreadable: {report_path}") from exc
    missing = [f for f in _REQUIRED_CHECK_FIELDS if not report.get(f)]
    if missing:
        raise ManifestError(
            f"pilot report has no completed check, missing {', '.join(missing)}")
    if report["decision"] != "proceed":
        raise ManifestError(
            f"pilot report decision is {report['decision']!r}, not 'proceed'")


def _preflight(corpus_dir: Path, entries: dict[str, ManifestEntry]) -> None:
    """Every `*.pdf` must have a manifest entry, its sha256 must match, and its
    `fetched_at` must parse -- all checked before any file is ingested, so one
    bad entry aborts the whole run rather than letting earlier files through."""
    problems: list[str] = []
    for pdf in sorted(corpus_dir.glob("*.pdf")):
        entry = entries.get(pdf.name)
        if entry is None:
            problems.append(f"{pdf.name}: no manifest entry")
            continue
        digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
        if digest != entry.sha256:
            problems.append(
                f"{pdf.name}: sha256 mismatch (file {digest}, manifest {entry.sha256})")
        try:
            parse_fetched_at(entry.fetched_at)
        except ProvenanceError as exc:
            problems.append(f"{pdf.name}: {exc}")
    if problems:
        raise ManifestError("manifest preflight failed: " + "; ".join(problems))


def _register_payload(session: Session, document_id) -> dict:
    return session.execute(
        select(AuditRecord.payload)
        .where(AuditRecord.document_id == document_id, AuditRecord.step == "register")
    ).scalar_one_or_none() or {}


def _check_provenance(session: Session, document_id, entry: ManifestEntry) -> str | None:
    """None when the `register` record carries this manifest's provenance;
    otherwise the reason it does not -- including the duplicate-delivery case,
    where `ingest()` returned an existing live document and the record belongs
    to whoever registered it first."""
    payload = _register_payload(session, document_id)
    fetched_at = parse_fetched_at(entry.fetched_at).isoformat()
    if payload.get("source_url") != entry.url:
        return f"register source_url {payload.get('source_url')!r} != manifest {entry.url!r}"
    if payload.get("fetched_at") != fetched_at:
        return f"register fetched_at {payload.get('fetched_at')!r} != manifest {fetched_at!r}"
    return None


def _advance(session: Session, store: ObjectStore, document_id, anonymizer,
            search_index, embedder) -> State:
    """Run the straat from the current state to a terminal one, including the
    OCR-recovery detour -- the same sequence `ingest_corpus()` runs inline, as
    its own function so a raised exception (a layer that did not run) leaves
    exactly the last *committed* transition standing."""
    state = process(session, document_id, store, anonymizer=anonymizer,
                    search_index=search_index, embedder=embedder)
    session.commit()
    if state == State.UNPROCESSABLE_OCR:
        state = recover(session, document_id, store)
        session.commit()
        if state == State.SUPERSEDED:
            owner = session.get(Document, document_id).superseded_by
            search_index.set_dossiers(str(owner), dossiers_of(session, owner))
        else:
            state = process(session, document_id, store, anonymizer=anonymizer,
                            search_index=search_index, embedder=embedder)
            session.commit()
    return state


def ingest_manifest_corpus(
    corpus_dir: Path,
    dossier: str,
    manifest_path: Path,
    pilot_report_path: Path,
    *,
    session_factory=None,
    store: ObjectStore | None = None,
    anonymizer=None,
    search_index=None,
    embedder=None,
) -> list[ManifestResult]:
    """Ingest every `*.pdf` in `corpus_dir` against `manifest_path`, gated by
    `WORDSWORTH_BACKEND_ENV` and a completed pilot check. Every guard that
    needs no backend runs first (`ManifestError` aborts before anything is
    ingested); only then are the real backends wired (or the injected test
    doubles used) and the straat run per file, with a read-back of the
    `register` record proving the manifest's provenance actually landed."""
    require_homelab_backend()
    require_completed_pilot_check(pilot_report_path)
    entries = read_manifest(manifest_path)
    _preflight(corpus_dir, entries)

    session_factory = session_factory or make_session_factory(make_engine())
    store = store or S3ObjectStore.from_config()
    anonymizer = anonymizer or OpenAnonymiserAnonymizer()
    search_index = search_index or OpenSearchIndex.from_config()
    embedder = embedder or OllamaEmbedder.from_config()

    results: list[ManifestResult] = []
    for pdf in sorted(corpus_dir.glob("*.pdf")):
        entry = entries[pdf.name]
        try:
            with session_factory() as session:
                doc = ingest(session, store, pdf.read_bytes(), filename=pdf.name,
                            dossier=dossier, source_url=entry.url,
                            fetched_at=parse_fetched_at(entry.fetched_at))
                session.commit()
                reason = _check_provenance(session, doc.id, entry)
                if reason is not None:
                    results.append(ManifestResult(pdf.name, False, reason))
                    continue
                state = _advance(session, store, doc.id, anonymizer, search_index, embedder)
                if state == State.INDEXED:
                    results.append(ManifestResult(pdf.name, True))
                else:
                    results.append(ManifestResult(
                        pdf.name, False, f"did not reach indexed: {state.value}"))
        except Exception as exc:  # a layer that did not run fails the run
            results.append(ManifestResult(pdf.name, False, type(exc).__name__))
        print(f"{pdf.name}: {results[-1].reason or 'ok'}")
    return results
