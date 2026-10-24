"""Manifest-driven corpus ingest: the stricter path `ingest_corpus.py
--manifest` takes.

Every check that CAN run before a byte is ingested runs first, in one
pre-flight pass, so a refusal never leaves a partial run behind: the backend
guard, the pilot's completed-check gate, every file listed, every sha256
matching. The read-back after each ingest is the proof that provenance
actually landed (`pipeline.ingest` silently keeps an existing document's old
provenance on a duplicate key -- see `design.md`), not a re-run of the logic
that wrote it.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import NamedTuple

from sqlalchemy import select

from .audit import current_state
from .db import make_engine, make_session_factory
from .embedder import OllamaEmbedder
from .manifest import ManifestEntry, load_check, read_manifest
from .models import AuditRecord
from .object_store import S3ObjectStore
from .openanonymiser_driver import OpenAnonymiserAnonymizer
from .opensearch_index import OpenSearchIndex
from .pipeline import ingest, process
from .states import State


class ManifestRunError(RuntimeError):
    """Refused before any file is ingested."""


class BackendGuardError(ManifestRunError):
    """`WORDSWORTH_BACKEND_ENV` is missing, empty, or not `homelab`."""


class UnlistedFileError(ManifestRunError):
    """A `*.pdf` in the corpus directory has no manifest entry."""


class Sha256MismatchError(ManifestRunError):
    """A file's sha256 differs from its manifest entry."""


class ManifestOutcome(NamedTuple):
    filename: str
    state: State
    ok: bool
    reason: str | None


def require_homelab_backend() -> None:
    """`WORDSWORTH_BACKEND_ENV` must be exactly `homelab` -- never inferred
    from a URL (both clusters use `*.svc.cluster.local`), never defaulted (a
    default is a silent fallback)."""
    value = os.environ.get("WORDSWORTH_BACKEND_ENV", "")
    if value != "homelab":
        raise BackendGuardError(
            "WORDSWORTH_BACKEND_ENV must be 'homelab' for a manifest run "
            f"(got {value!r})")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_back(session, document_id, entry: ManifestEntry) -> str | None:
    """The `register` audit payload for this document, compared with the
    manifest. Returns the failure reason, or None when it matches."""
    payload = session.execute(
        select(AuditRecord.payload)
        .where(AuditRecord.document_id == document_id, AuditRecord.step == "register")
        .order_by(AuditRecord.seq).limit(1)
    ).scalar_one_or_none() or {}
    recorded_url = payload.get("source_url")
    recorded_fetched_at = payload.get("fetched_at")
    if recorded_url != entry.url:
        return f"recorded source_url {recorded_url!r} != manifest {entry.url!r}"
    if recorded_fetched_at != entry.fetched_at.isoformat():
        return (f"recorded fetched_at {recorded_fetched_at!r} != manifest "
                f"{entry.fetched_at.isoformat()!r}")
    return None


def _advance(session_factory, store, anonymizer, index, embedder, filename,
             data, dossier, entry: ManifestEntry) -> ManifestOutcome:
    with session_factory() as session:
        doc = ingest(session, store, data, filename=filename, dossier=dossier,
                      source_url=entry.url, fetched_at=entry.fetched_at)
        session.commit()
        try:
            state = process(session, doc.id, store, anonymizer=anonymizer,
                             search_index=index, embedder=embedder)
            session.commit()
        except Exception as exc:
            session.rollback()
            # The real committed state, not a synthetic FAILED: a retry-
            # exhausted anonymize leaves the document REGISTERED (process()
            # never commits EXTRACTED on that path), and the caller should see
            # that, not a state the pipeline never actually reached.
            state = current_state(session, doc.id)
            reason = f"layer failed: {type(exc).__name__}: {exc}"
            print(f"{filename}: {reason}")
            return ManifestOutcome(filename, state, False, reason)

        reason = _read_back(session, doc.id, entry)
        if reason is not None:
            print(f"{filename}: {state.value}, provenance mismatch: {reason}")
            return ManifestOutcome(filename, state, False, reason)
        if state != State.INDEXED:
            reason = f"terminal state {state.value}, not indexed"
            print(f"{filename}: {reason}")
            return ManifestOutcome(filename, state, False, reason)
        print(f"{filename}: {state.value}")
        return ManifestOutcome(filename, state, True, None)


def ingest_manifest_corpus(
    corpus_dir: Path, dossier: str, manifest_path: Path, *,
    session_factory=None, store=None, anonymizer=None, search_index=None,
    embedder=None,
) -> list[ManifestOutcome]:
    """Ingest every ``*.pdf`` in ``corpus_dir`` against ``manifest_path``,
    homelab backends only, read back and compared after each ingest.

    The optional backend/session-factory parameters are the injection seam
    for tests; a CLI run leaves them ``None`` and gets the real, configured
    backends (mirrors `pipeline.process`)."""
    require_homelab_backend()
    load_check(manifest_path)
    manifest = read_manifest(manifest_path)

    pdfs = sorted(corpus_dir.glob("*.pdf"))
    unlisted = [p.name for p in pdfs if p.name not in manifest]
    if unlisted:
        raise UnlistedFileError(f"PDF(s) not in manifest, aborting: {unlisted}")

    contents = {p.name: p.read_bytes() for p in pdfs}
    mismatches = [
        f"{name} (file={_sha256(data)} manifest={manifest[name].sha256})"
        for name, data in contents.items() if _sha256(data) != manifest[name].sha256
    ]
    if mismatches:
        raise Sha256MismatchError(f"sha256 mismatch, aborting: {mismatches}")

    session_factory = session_factory or make_session_factory(make_engine())
    store = store or S3ObjectStore.from_config()
    anonymizer = anonymizer or OpenAnonymiserAnonymizer()
    index = search_index or OpenSearchIndex.from_config()
    embedder = embedder or OllamaEmbedder.from_config()
    index.ensure_ready()

    return [
        _advance(session_factory, store, anonymizer, index, embedder, name,
                 contents[name], dossier, manifest[name])
        for name in sorted(contents)
    ]
