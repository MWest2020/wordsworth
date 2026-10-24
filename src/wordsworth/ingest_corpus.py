"""Production corpus ingestion — the full Wordsworth straat on real corpora.

Walks a directory of PDFs and drives each through
``ingest → OCR recovery (if scanned) → anonymize → store → index``, wired to the
sovereign backends from config: the S3 object store, the OpenAnonymiser GLiNER
service (``WORDSWORTH_OPENANONYMISER_URL``) for entity PII, OpenSearch, and
Ollama (bge-m3) embeddings.

Unlike the eval harness this uses the real S3 store and the OpenAnonymiser
anonymizer (not the regex-only ``DeterministicAnonymizer`` default). Every
failure is loud — no clear-text pass-through, no silent skip.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .db import make_engine, make_session_factory
from .embedder import OllamaEmbedder
from .ingest_manifest import ingest_manifest_corpus
from .manifest import ManifestError
from .object_store import S3ObjectStore
from .openanonymiser_driver import OpenAnonymiserAnonymizer
from .opensearch_index import OpenSearchIndex
from .models import Document
from .pipeline import dossiers_of, ingest, process
from .recovery import recover
from .states import State


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
            state = process(session, doc.id, store, anonymizer=anonymizer,
                            search_index=index, embedder=embedder)
            session.commit()
            if state == State.UNPROCESSABLE_OCR:
                # Scanned page: OCR to a text layer, then resume the straat.
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
    # Pilot-only path (pilot-ingest-manifest): stricter rules, proved
    # provenance, and the homelab-only guard — see docs/reference/ingest.md.
    parser.add_argument("--manifest", type=Path, default=None,
                        help="Per-file provenance (file/url/fetched_at/sha256/"
                             "bytes/status/ok, one JSON object per line). "
                             "Requires --pilot-report and WORDSWORTH_BACKEND_ENV=homelab.")
    parser.add_argument("--pilot-report", type=Path, default=None,
                        help="Pilot check (who/when/robots/terms/anubis/decision). "
                             "Required with --manifest.")
    args = parser.parse_args(argv)
    if not args.corpus_dir.is_dir():
        print(f"corpus-dir not found: {args.corpus_dir}", file=sys.stderr)
        return 2

    if args.manifest is not None:
        if args.pilot_report is None:
            print("--pilot-report is required with --manifest", file=sys.stderr)
            return 2
        try:
            results = ingest_manifest_corpus(args.corpus_dir, args.dossier,
                                             args.manifest, args.pilot_report)
        except ManifestError as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 2
        ok = sum(1 for r in results if r.ok)
        print(f"\n{ok}/{len(results)} ok")
        return 0 if results and ok == len(results) else 1

    results = ingest_corpus(args.corpus_dir, args.dossier)
    indexed = sum(1 for _, s in results if s == State.INDEXED)
    print(f"\n{indexed}/{len(results)} indexed")
    return 0 if results and indexed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
