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
from .object_store import S3ObjectStore
from .openanonymiser_driver import OpenAnonymiserAnonymizer
from .opensearch_index import OpenSearchIndex
from .pipeline import ingest, process
from .recovery import recover
from .states import State


def ingest_corpus(corpus_dir: Path) -> list[tuple[str, State]]:
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
            doc = ingest(session, store, pdf.read_bytes())
            session.commit()
            state = process(session, doc.id, store, anonymizer=anonymizer,
                            search_index=index, embedder=embedder)
            session.commit()
            if state == State.UNPROCESSABLE_OCR:
                # Scanned page: OCR to a text layer, then resume the straat.
                recover(session, doc.id, store)
                session.commit()
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
    args = parser.parse_args(argv)
    if not args.corpus_dir.is_dir():
        print(f"corpus-dir not found: {args.corpus_dir}", file=sys.stderr)
        return 2
    results = ingest_corpus(args.corpus_dir)
    indexed = sum(1 for _, s in results if s == State.INDEXED)
    print(f"\n{indexed}/{len(results)} indexed")
    return 0 if results and indexed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
