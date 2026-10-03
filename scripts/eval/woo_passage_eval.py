# SPDX-License-Identifier: MIT
"""Candidate 2 of long-documents-rank-fairly, offline, in one pool.

Passages exist only for the Woo documents, so every configuration is measured
inside the same pool of those documents -- the production ranking included --
and not against the full index with its extra distractors. Absolute numbers
are therefore higher than in `woo_ranking_eval.py`; the comparison between
configurations is what this run is for.

- BM25: OpenSearch, the production query, filtered to the pool's ids.
- kNN: exact cosine in-process (production uses HNSW, approximate).
- Passage vectors: `wordsworth.eval.passages`, embedded through the production
  Ollama Service and cached in CACHE so a dropped run resumes.

Read-only for production: nothing is written to the corpus, index or trail.

    python scripts/eval/woo_passage_eval.py herkomst.jsonl CACHE.json
"""
import json
import sys
import time
from pathlib import Path

from sqlalchemy import select
from zeef.similarity import cosine

from wordsworth.db import make_engine, make_session_factory
from wordsworth.embedder import OllamaEmbedder
from wordsworth.eval.passages import STRIDE, WORDS, best_passage_scores, split
from wordsworth.eval.woo_collection import build, score
from wordsworth.models import Document
from wordsworth.opensearch_index import OpenSearchIndex, _bm25
from wordsworth.rrf import fuse_ranked_ids

DEPTH = 50


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def main(herkomst: Path, cache: Path):
    with make_session_factory(make_engine())() as session:
        queries, lengths, info = build(herkomst, session)
        key_to_id = {k: str(i) for i, k in session.execute(
            select(Document.id, Document.object_key).where(
                Document.object_key.in_(list(lengths)), Document.superseded_by.is_(None)))}
    id_to_key = {i: k for k, i in key_to_id.items()}
    ids = list(id_to_key)

    index = OpenSearchIndex.from_config()
    client, name = index._client, index._index
    docs = {d["_id"]: d["_source"] for d in client.mget(
        body={"ids": ids}, index=name, _source=["text", "vector"])["docs"] if d.get("found")}
    emb = OllamaEmbedder.from_config()

    passages = json.loads(cache.read_text()) if cache.exists() else {}
    started, todo = time.time(), [i for i in ids if i not in passages and i in docs]
    log(f"pool {len(ids)} documents, {len(todo)} to embed in passages")
    for n, doc_id in enumerate(todo, 1):
        passages[doc_id] = [emb.embed([p])[0] for p in split(docs[doc_id].get("text") or "")]
        cache.write_text(json.dumps(passages))
        if n % 10 == 0:
            log(f"  {n}/{len(todo)} documents, {sum(map(len, passages.values()))} passages, "
                f"{round(time.time() - started)} s")
    embed_seconds = round(time.time() - started)

    qvec = {}

    def vec(text):
        if text not in qvec:
            qvec[text] = emb.embed([text])[0]
        return qvec[text]

    def bm25(text):
        body = {"query": {"bool": {"must": [_bm25(text)], "filter": [{"ids": {"values": ids}}]}},
                "size": DEPTH, "_source": False}
        return [h["_id"] for h in client.search(index=name, body=body)["hits"]["hits"]]

    def knn_doc(qv):
        return sorted((i for i in ids if docs.get(i, {}).get("vector")),
                      key=lambda i: cosine(qv, docs[i]["vector"]), reverse=True)[:DEPTH]

    def knn_pass(qv):
        s = best_passage_scores(qv, passages)
        return sorted(s, key=s.get, reverse=True)[:DEPTH]

    def keys(order):
        return [id_to_key[i] for i in order]

    def ranker(kind):
        def run(text):
            qv = vec(text)
            if kind == "bm25":
                return keys(bm25(text))
            if kind in ("cosine", "rrf"):
                recall = fuse_ranked_ids([bm25(text), knn_doc(qv)])[:DEPTH]
                if kind == "cosine":
                    recall.sort(key=lambda i: cosine(qv, docs[i]["vector"]), reverse=True)
                return keys(recall)
            recall = fuse_ranked_ids([bm25(text), knn_pass(qv)])[:DEPTH]
            if kind == "passage cosine":
                s = best_passage_scores(qv, {i: passages[i] for i in recall if i in passages})
                recall.sort(key=lambda i: s.get(i, -1.0), reverse=True)
            return keys(recall)
        return run

    report = {"collection": {k: v for k, v in info.items() if k != "unmatched"},
              "passages": {"words": WORDS, "stride": STRIDE,
                           "count": sum(map(len, passages.values())),
                           "embed_seconds_this_run": embed_seconds},
              "pool": len(ids)}
    for kind, label in (("cosine", "cosine, whole-document (production shape)"),
                        ("rrf", "rrf, whole-document (candidate 1)"),
                        ("passage rrf", "rrf, passages (candidate 2a)"),
                        ("passage cosine", "best-passage cosine (candidate 2b)"),
                        ("bm25", "bm25 alone (reference)")):
        report[label] = score(ranker(kind), queries, lengths)
        log(f"scored {label}")
    print(json.dumps(report, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
