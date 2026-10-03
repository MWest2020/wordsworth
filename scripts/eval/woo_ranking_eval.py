# SPDX-License-Identifier: MIT
"""Ranking on the real Woo corpus, by length (change long-documents-rank-fairly).

Builds the derived collection (`wordsworth.eval.woo_collection`) from
`herkomst.jsonl` and the live documents, writes it as `queries.tsv` +
`qrels.txt`, and scores a ranker on it: Recall@8 (the k `/ask` uses), MRR over
the top 50, nDCG@10 -- overall and per length third. Read-only: it writes
nothing to the corpus, the index or the audit trail.

    python scripts/eval/woo_ranking_eval.py herkomst.jsonl OUT_DIR

Needs the database, OpenSearch and Ollama, so it runs where the api runs.
"""
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from sqlalchemy import func, select

from wordsworth.db import make_engine, make_session_factory
from wordsworth.embedder import OllamaEmbedder
from wordsworth.eval.adapters import bm25_adapter, hybrid_adapter
from wordsworth.eval.metrics import ndcg_at_k, recall_at_k
from wordsworth.eval.woo_collection import (query_from_decision, query_from_filename,
                                            reciprocal_rank, thirds)
from wordsworth.models import Document, DocumentText
from wordsworth.opensearch_index import OpenSearchIndex

DEPTH = 50   # how deep the ranking is read for MRR: the hybrid recall set


def build(herkomst: Path, session):
    rows = [json.loads(line) for line in herkomst.read_text().splitlines() if line.strip()]
    live = {f: (k, n) for f, k, n in session.execute(
        select(Document.filename, Document.object_key,
               func.length(DocumentText.anonymized_text))
        .join(DocumentText, DocumentText.document_id == Document.id)
        .where(Document.superseded_by.is_(None), Document.filename.is_not(None)))}
    unmatched = [r["bestand"] for r in rows if r["bestand"] not in live]
    rows = [r for r in rows if r["bestand"] in live]
    lengths = {live[r["bestand"]][0]: live[r["bestand"]][1] or 0 for r in rows}

    known, skipped = defaultdict(set), 0
    for r in rows:
        q = query_from_filename(r["bestand"])
        if q is None:
            skipped += 1
        else:
            known[q].add(live[r["bestand"]][0])
    decisions = defaultdict(set)
    for r in rows:
        decisions[query_from_decision(r["besluit"])].add(live[r["bestand"]][0])

    queries = {}
    for i, (text, rel) in enumerate(sorted(known.items())):
        queries[f"K{i:03d}"] = (text, rel)
    for i, (text, rel) in enumerate(sorted(decisions.items())):
        queries[f"D{i:02d}"] = (text, rel)
    info = {"documents": len(rows), "unmatched": unmatched,
            "skipped_no_subject": skipped, "known_item_queries": len(known),
            "known_item_single": sum(1 for r in known.values() if len(r) == 1),
            "decision_queries": len(decisions)}
    return queries, lengths, info


def write(out: Path, queries):
    out.mkdir(parents=True, exist_ok=True)
    (out / "queries.tsv").write_text(
        "".join(f"{qid}\t{text}\n" for qid, (text, _) in queries.items()))
    (out / "qrels.txt").write_text(
        "".join(f"{qid} 0 {doc} 1\n" for qid, (_, rel) in queries.items() for doc in sorted(rel)))


def score(ranker, queries, lengths):
    third = thirds(lengths)
    rows = []
    for qid, (text, rel) in queries.items():
        ranked = ranker(text)
        qrels = {d: 1 for d in rel}
        rows.append({"qid": qid, "recall@8": recall_at_k(ranked, qrels, 8),
                     "mrr": reciprocal_rank(ranked, rel),
                     "ndcg@10": ndcg_at_k(ranked, qrels, 10),
                     # A single-document known item belongs to that document's third.
                     "third": third[next(iter(rel))] if qid.startswith("K") and len(rel) == 1 else None})

    def mean(rs, key):
        return round(statistics.mean(r[key] for r in rs), 3) if rs else None

    out = {}
    groups = {"known-item": [r for r in rows if r["qid"].startswith("K")],
              "decision": [r for r in rows if r["qid"].startswith("D")]}
    for t in ("short", "middle", "long"):
        groups[f"known-item {t}"] = [r for r in rows if r["third"] == t]
    for name, rs in groups.items():
        out[name] = {"n": len(rs), **{k: mean(rs, k) for k in ("recall@8", "mrr", "ndcg@10")}}
    return out


def main(argv):
    herkomst, out = Path(argv[0]), Path(argv[1])
    with make_session_factory(make_engine())() as session:
        queries, lengths, info = build(herkomst, session)
    write(out, queries)
    t = thirds(lengths)
    bounds = {k: (min(lengths[i] for i in t if t[i] == k), max(lengths[i] for i in t if t[i] == k))
              for k in ("short", "middle", "long")}
    index, emb = OpenSearchIndex.from_config(), OllamaEmbedder.from_config()
    report = {"collection": info, "length_thirds_chars": bounds,
              "hybrid cosine (production)": score(
                  hybrid_adapter(index, emb, k=DEPTH, final="cosine"), queries, lengths),
              "hybrid rrf (candidate 1)": score(
                  hybrid_adapter(index, emb, k=DEPTH, final="rrf"), queries, lengths),
              "bm25 (reference)": score(bm25_adapter(index, k=DEPTH), queries, lengths)}
    print(json.dumps(report, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1:])
