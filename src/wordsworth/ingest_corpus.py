"""Production corpus ingestion — the full Wordsworth straat on real corpora.

Walks a directory of PDFs and drives each through
``ingest → OCR recovery (if scanned) → anonymize → store → index``, wired to the
sovereign backends from config: the S3 object store, the OpenAnonymiser GLiNER
service (``WORDSWORTH_OPENANONYMISER_URL``) for entity PII, OpenSearch, and
Ollama (bge-m3) embeddings.

Unlike the eval harness this uses the real S3 store and the OpenAnonymiser
anonymizer (not the regex-only ``DeterministicAnonymizer`` default). Every
failure is loud — no clear-text pass-through, no silent skip.

``--manifest`` (pilot-ingest-manifest) adds a stricter, provenance-proving
path for one fetched corpus: every ``*.pdf`` must have a manifest entry, its
sha256 must match, ``source_url``/``fetched_at`` come from the manifest (never
the ingest time), and each document's ``register`` audit record is read back
afterwards to prove the provenance actually landed. See
``docs/reference/ingest.md``.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from .anonymizer import Anonymizer
from .backend_guard import BackendGuardError, require_homelab_backends
from .db import make_engine, make_session_factory
from .embedder import Embedder, OllamaEmbedder
from .manifest import ManifestError, read_manifest
from .object_store import ObjectStore, S3ObjectStore
from .openanonymiser_driver import OpenAnonymiserAnonymizer
from .opensearch_index import OpenSearchIndex
from .pilot_report import PilotReportError, require_completed_check
from .models import Document
from .pipeline import dossiers_of, ingest, process, register_payload
from .recovery import recover
from .search_index import SearchIndex
from .states import State


def _advance(session, store: ObjectStore, index: SearchIndex, embedder: Embedder,
            anonymizer: Anonymizer, doc: Document) -> State:
    """Run `process()`, recovering through OCR once if the born-digital pass
    needs it. Shared by the plain and manifest-driven corpus walk."""
    state = process(session, doc.id, store, anonymizer=anonymizer,
                    search_index=index, embedder=embedder)
    session.commit()
    if state == State.UNPROCESSABLE_OCR:
        state = recover(session, doc.id, store)
        session.commit()
        if state == State.SUPERSEDED:
            # Its OCR'd PDF is already a document, which now holds the
            # dossiers (one-document-per-object).
            owner = session.get(Document, doc.id).superseded_by
            index.set_dossiers(str(owner), dossiers_of(session, owner))
        else:
            state = process(session, doc.id, store, anonymizer=anonymizer,
                            search_index=index, embedder=embedder)
            session.commit()
    return state


def ingest_corpus(corpus_dir: Path, dossier: str) -> list[tuple[str, State]]:
    """Ingest every ``*.pdf`` in ``corpus_dir`` through the full straat.

    Returns ``(filename, terminal_state)`` per document. Backends are the real
    sovereign ones resolved from config; the anonymizer is the OpenAnonymiser
    GLiNER driver (structured PII via the deterministic pass it composes, entity
    PII via the service)."""
    engine = make_engine()
    session_factory = make_session_factory(engine)
    store = S3ObjectStore.from_config()
    anonymizer = OpenAnonymiserAnonymizer()
    index = OpenSearchIndex.from_config()
    embedder = OllamaEmbedder.from_config()
    index.ensure_ready()

    results: list[tuple[str, State]] = []
    for pdf in sorted(corpus_dir.glob("*.pdf")):
        with session_factory() as session:
            doc = ingest(session, store, pdf.read_bytes(), filename=pdf.name,
                         dossier=dossier)
            session.commit()
            state = _advance(session, store, index, embedder, anonymizer, doc)
            results.append((pdf.name, state))
            print(f"{pdf.name}: {state.value}")
    return results


def ingest_manifest_corpus(
    corpus_dir: Path,
    dossier: str,
    manifest_path: Path,
    pilot_report_path: Path,
    *,
    session_factory=None,
    store: ObjectStore | None = None,
    anonymizer: Anonymizer | None = None,
    index: SearchIndex | None = None,
    embedder: Embedder | None = None,
) -> list[tuple[str, State]]:
    """Ingest a fetched corpus against a manifest, and prove the provenance
    arrived (pilot-ingest-manifest).

    Every check that can run before a file is touched does: the pilot report's
    completed check, the backends being homelab, every ``*.pdf`` having a
    manifest entry, and every entry's sha256 matching the file. After each
    ingest, the ``register`` audit record is read back; a document whose
    recorded provenance does not match the manifest (including one that was
    already a live document under other provenance) fails with the reason and
    is not reprocessed. The caller's ``store``/``anonymizer``/``index``/
    ``embedder``/``session_factory`` are test seams; the default is the real
    sovereign backends, as in `ingest_corpus`."""
    require_completed_check(pilot_report_path)
    require_homelab_backends()

    entries = read_manifest(manifest_path)
    pdfs = sorted(corpus_dir.glob("*.pdf"))
    unlisted = [p.name for p in pdfs if p.name not in entries]
    if unlisted:
        raise ManifestError(
            "corpus file(s) with no manifest entry, nothing ingested: "
            + ", ".join(unlisted))
    mismatched = []
    for pdf in pdfs:
        digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
        if digest != entries[pdf.name].sha256:
            mismatched.append(
                f"{pdf.name} (file sha256 {digest}, manifest {entries[pdf.name].sha256})")
    if mismatched:
        raise ManifestError("sha256 mismatch, nothing ingested: " + "; ".join(mismatched))

    if session_factory is None:
        session_factory = make_session_factory(make_engine())
    store = store or S3ObjectStore.from_config()
    anonymizer = anonymizer or OpenAnonymiserAnonymizer()
    index = index or OpenSearchIndex.from_config()
    embedder = embedder or OllamaEmbedder.from_config()
    index.ensure_ready()

    results: list[tuple[str, State]] = []
    for pdf in pdfs:
        entry = entries[pdf.name]
        with session_factory() as session:
            doc = ingest(session, store, pdf.read_bytes(), filename=pdf.name,
                         dossier=dossier, source_url=entry.url,
                         fetched_at=entry.fetched_at)
            session.commit()

            recorded = register_payload(session, doc.id)
            if (recorded.get("source_url") != entry.url
                    or recorded.get("fetched_at") != entry.fetched_at.isoformat()):
                reason = (
                    f"provenance mismatch: recorded "
                    f"{recorded.get('source_url')!r}/{recorded.get('fetched_at')!r}, "
                    f"manifest {entry.url!r}/{entry.fetched_at.isoformat()!r}")
                print(f"{pdf.name}: failed ({reason})")
                results.append((pdf.name, State.FAILED))
                continue

            state = _advance(session, store, index, embedder, anonymizer, doc)
            results.append((pdf.name, state))
            print(f"{pdf.name}: {state.value}")
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ingest a PDF corpus through the full Wordsworth straat "
                    "(anonymize via the OpenAnonymiser GLiNER service)."
    )
    parser.add_argument("--corpus-dir", required=True, type=Path,
                        help="Directory of *.pdf files to ingest.")
    # Required, with no default: a document in no dossier is invisible to every
    # scoped search, so an optional flag would quietly make unfindable documents.
    parser.add_argument("--dossier", required=True,
                        help="The dossier these documents belong to.")
    parser.add_argument("--manifest", type=Path, default=None,
                        help="JSONL provenance manifest (bestand/url/"
                            "fetched_at/sha256 per file). An unlisted *.pdf "
                            "aborts the run, sha256 is checked, and provenance "
                            "is read back after each ingest. Requires "
                            "--pilot-report, and homelab backends only.")
    parser.add_argument("--pilot-report", type=Path, default=None,
                        help="Pilot check report (who/when/robots_txt/terms/"
                            "anubis_status/decision); required with "
                            "--manifest.")
    args = parser.parse_args(argv)
    if not args.corpus_dir.is_dir():
        print(f"corpus-dir not found: {args.corpus_dir}", file=sys.stderr)
        return 2
    if args.manifest and not args.pilot_report:
        print("--manifest requires --pilot-report", file=sys.stderr)
        return 2

    if args.manifest:
        try:
            results = ingest_manifest_corpus(args.corpus_dir, args.dossier,
                                             args.manifest, args.pilot_report)
        except (ManifestError, PilotReportError, BackendGuardError) as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 1
    else:
        results = ingest_corpus(args.corpus_dir, args.dossier)

    indexed = sum(1 for _, s in results if s == State.INDEXED)
    print(f"\n{indexed}/{len(results)} indexed")
    return 0 if results and indexed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
