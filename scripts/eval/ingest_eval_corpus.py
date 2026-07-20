"""Ingest een evaluatiecorpus in wordsworth, gekeyd op de qrels-doc-ids.

Operator-tooling voor de evaluatierun (docs/reference/evaluation.md):
elk PDF-bestand `<docid>.pdf` in --corpus-dir wordt geregistreerd met
object_key == <docid>, door de NORMALE pipeline gehaald (extract →
anonymize → index) en belandt zo in OpenSearch onder het externe id dat
de qrels gebruiken. Read-only t.o.v. productie: eigen database (--db-url)
en eigen index (WORDSWORTH_OPENSEARCH_INDEX).

Gebruik:
  uv run python scripts/eval/ingest_eval_corpus.py --corpus-dir ./corpus \
      --db-url postgresql+psycopg://... [--embedder ollama|fake]

--embedder ollama  → echte bge-m3-vectoren (vereist lokale Ollama; nodig
                     voor de hybrid-config van de eval). DEFAULT.
--embedder fake    → DeterministicEmbedder: vectoren zijn betekenisloos.
                     ALLEEN geldig als de eval uitsluitend --config bm25
                     draait (BM25 kijkt niet naar vectoren). Een hybrid-run
                     op fake vectoren is misleidend — niet doen.

Een document dat niet verwerkt kan worden is een harde fout in de output
(geen stille overslag), maar stopt de batch niet: het rapport onderaan
telt per eindtoestand.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from wordsworth.db import init_schema, make_engine, make_session_factory
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.opensearch_index import OpenSearchIndex
from wordsworth.pipeline import process, register


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus-dir", required=True, type=Path)
    ap.add_argument("--db-url", required=True)
    ap.add_argument("--embedder", choices=["ollama", "fake"], default="ollama")
    args = ap.parse_args()

    pdfs = sorted(args.corpus_dir.glob("*.pdf"))
    if not pdfs:
        print(f"geen PDF's in {args.corpus_dir}", file=sys.stderr)
        return 2

    if args.embedder == "ollama":
        from wordsworth.embedder import OllamaEmbedder

        embedder = OllamaEmbedder.from_config()
    else:
        from wordsworth.embedder import DeterministicEmbedder
        from wordsworth.config import settings

        print("LET OP: fake embedder — vectoren betekenisloos; eval alleen "
              "met --config bm25 draaien.", file=sys.stderr)
        embedder = DeterministicEmbedder(dim=settings.embedding_dim)

    engine = make_engine(args.db_url)
    init_schema(engine)
    session_factory = make_session_factory(engine)

    index = OpenSearchIndex.from_config()
    store = InMemoryObjectStore()  # bytes zijn alleen nodig tijdens deze run
    states: Counter[str] = Counter()
    failures: list[tuple[str, str]] = []

    with session_factory() as session:
        pending: list[tuple[str, object]] = []
        for pdf in pdfs:
            doc_id = pdf.stem  # qrels-id == bestandsnaam zonder .pdf
            store.put(doc_id, pdf.read_bytes())
            doc = register(session, doc_id)
            session.commit()
            pending.append((doc_id, doc.id))

        # process is hervatbaar: indexfalen is transient, dus retry-rondes
        # pakken een document op waar de audit-trail zegt dat het gebleven is.
        for attempt in range(1, 4):
            still: list[tuple[str, object]] = []
            for doc_id, uuid in pending:
                try:
                    state = process(
                        session, uuid, store,
                        search_index=index, embedder=embedder,
                    )
                    session.commit()
                    states[str(state)] += 1
                except Exception as exc:
                    session.rollback()
                    still.append((doc_id, uuid))
                    if attempt == 3:
                        states["FAILED"] += 1
                        failures.append((doc_id, f"{type(exc).__name__}: {exc}"))
            pending = still
            if not pending:
                break
            print(f"retry-ronde {attempt}: {len(pending)} documenten opnieuw",
                  file=sys.stderr)
            import time
            time.sleep(10 * attempt)

    print(f"\ningest-rapport ({len(pdfs)} documenten):")
    for state, n in sorted(states.items()):
        print(f"  {state}: {n}")
    for doc_id, err in failures:
        print(f"  FAILED {doc_id}: {err}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
