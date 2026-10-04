# SPDX-License-Identifier: MIT
"""`wordsworth-backfill-passages`: give every indexed document its passages.

New and reprocessed documents get passages when they are indexed; the ones
indexed before passages existed do not. This fills them in, so the passage kNN
half (`WORDSWORTH_HYBRID_KNN=passage`) sees the whole corpus -- a document
without passages is invisible to it.

- **Partial updates only** (`set_passages`): the text and the document vector
  are never rewritten. Rewriting the whole document is how 770 documents lost
  their vectors on 2026-09-18.
- **Resumable:** it asks the index what is still missing, so a stopped run
  continues where it was.
- **It ends:** a document with no text has no passages, and one whose
  embedding fails after the retry budget is set aside; both are counted and
  reported, not retried forever.
- ``--workers`` defaults to 2: one per Ollama instance. Each instance takes one
  request per model at a time, so more workers only queue.
"""
from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from .passages import embed_passages


def run(index, embedder, *, workers: int = 2, batch: int = 50, log=print) -> dict:
    stats = {"documents": 0, "passages": 0, "empty": 0, "failed": 0}
    skip: set[str] = set()
    started = time.time()
    while True:
        todo = [(d, t) for d, t in index.missing_passages(limit=batch + len(skip))
                if d not in skip][:batch]
        if not todo:
            break
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(embed_passages, embedder, text): doc for doc, text in todo}
            for future in as_completed(futures):
                doc = futures[future]
                try:
                    vectors = future.result()
                except Exception as exc:     # after embed_passages' own retries
                    skip.add(doc)
                    stats["failed"] += 1
                    log(f"failed {doc}: {type(exc).__name__}")
                    continue
                if not vectors:
                    skip.add(doc)
                    stats["empty"] += 1
                    continue
                if index.set_passages(doc, vectors):
                    stats["documents"] += 1
                    stats["passages"] += len(vectors)
        log(f"{stats['documents']} documents, {stats['passages']} passages, "
            f"{round(time.time() - started)} s")
    stats["seconds"] = round(time.time() - started)
    return stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="wordsworth-backfill-passages",
                                 description=__doc__.split("\n")[0])
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--batch", type=int, default=50)
    args = ap.parse_args(argv)
    from .embedder import OllamaEmbedder
    from .opensearch_index import OpenSearchIndex
    index = OpenSearchIndex.from_config()
    index.ensure_ready()          # declares the passages field on an older index
    stats = run(index, OllamaEmbedder.from_config(), workers=args.workers,
                batch=args.batch, log=lambda m: print(m, flush=True))
    print(stats, flush=True)
    return 1 if stats["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
