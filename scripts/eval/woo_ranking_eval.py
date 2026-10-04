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
import sys
from pathlib import Path

from wordsworth.db import make_engine, make_session_factory
from wordsworth.embedder import OllamaEmbedder
from wordsworth.eval.adapters import bm25_adapter, hybrid_adapter
from wordsworth.eval.woo_collection import build, score, thirds
from wordsworth.opensearch_index import OpenSearchIndex

DEPTH = 50   # how deep the ranking is read for MRR: the hybrid recall set


def write(out: Path, queries):
    out.mkdir(parents=True, exist_ok=True)
    (out / "queries.tsv").write_text(
        "".join(f"{qid}\t{text}\n" for qid, (text, _) in queries.items()))
    (out / "qrels.txt").write_text(
        "".join(f"{qid} 0 {doc} 1\n" for qid, (_, rel) in queries.items() for doc in sorted(rel)))


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
              "hybrid cosine, document kNN": score(
                  hybrid_adapter(index, emb, k=DEPTH, final="cosine", knn="document"),
                  queries, lengths),
              "hybrid rrf, document kNN (candidate 1)": score(
                  hybrid_adapter(index, emb, k=DEPTH, final="rrf", knn="document"),
                  queries, lengths),
              "hybrid rrf, passage kNN (candidate 2a)": score(
                  hybrid_adapter(index, emb, k=DEPTH, final="rrf", knn="passage"),
                  queries, lengths),
              "bm25 (reference)": score(bm25_adapter(index, k=DEPTH), queries, lengths)}
    print(json.dumps(report, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1:])
