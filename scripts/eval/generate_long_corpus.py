# SPDX-License-Identifier: MIT
"""Generate a long synthetic PDF corpus with page-level ground truth
(synthetic-long-corpus).

Real Woo publications are long PDFs; the existing ~500-short-text corpus
(generate_ground_truth.py) cannot test page boundaries, long-document
ranking or pages without a text layer. This writes:

  documents/<doc-id>.pdf  born-digital PDFs, a fraction of their pages
                          scanned (image-only) per --scanned
  gold.jsonl              one line per born-digital page, for
                          `python -m wordsworth.eval.pii_run`
  gold_scanned.jsonl      the same, for the scanned pages -- kept apart,
                          because pii_run never opens a PDF and would
                          otherwise score pages the pipeline cannot see
  queries.tsv / qrels.txt one query per document, answered by a phrase
                          planted on a page at or after page 20
  manifest.json           what was seeded, so a measurement can be checked

Read the caveat in the manifest before quoting any score.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from wordsworth.eval.long_corpus import DocResult, PageGold, build_document


def _write_gold(path: Path, pages: list[PageGold]) -> None:
    path.write_text(
        "".join(json.dumps(p.record(), ensure_ascii=False) + "\n" for p in pages),
        encoding="utf-8")


def _write_queries(queries_path: Path, qrels_path: Path, results: list[DocResult]) -> None:
    all_ids = [r.doc_id for r in results]
    q_lines, qrel_lines = [], []
    for r in results:
        qid = f"q-{r.doc_id}"
        q_lines.append(f"{qid}\t{r.answer_phrase}\n")
        qrel_lines.extend(f"{qid} 0 {other} {1 if other == r.doc_id else 0}\n"
                          for other in all_ids)
    queries_path.write_text("".join(q_lines), encoding="utf-8")
    qrels_path.write_text("".join(qrel_lines), encoding="utf-8")


def _type_counts(pages: list[PageGold]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for p in pages:
        for e in p.entities:
            counts[e["type"]] = counts.get(e["type"], 0) + 1
    return dict(sorted(counts.items()))


def _write_manifest(path: Path, args: argparse.Namespace, results: list[DocResult]) -> None:
    manifest = {
        "seed": args.seed,
        "docs": args.docs,
        "pages": args.pages,
        "scanned": args.scanned,
        "counts": {
            "gold.jsonl": _type_counts([p for r in results for p in r.gold_pages]),
            "gold_scanned.jsonl": _type_counts(
                [p for r in results for p in r.gold_scanned_pages]),
        },
        "pages_per_document": {r.doc_id: args.pages for r in results},
        "scanned_pages_per_document": {r.doc_id: r.scanned_pages for r in results},
        "queries": [{"query_id": f"q-{r.doc_id}", "doc_id": r.doc_id,
                     "answer_page": r.answer_page, "answer_phrase": r.answer_phrase}
                    for r in results],
        "caveat": ("Synthetic. Written by us and more regular than administrative "
                   "reality: a score here is a lower bound for the machinery, not a "
                   "prediction for production text. gold_scanned.jsonl is not part of "
                   "any score to quote: pii_run detects over gold text and never opens "
                   "a PDF, so scoring a scanned page would count a page the pipeline "
                   "cannot see as if extraction were perfect."),
    }
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("outdir", type=Path)
    ap.add_argument("--docs", type=int, default=30)
    ap.add_argument("--pages", type=int, default=30)
    ap.add_argument("--seed", type=int, default=20261115)
    ap.add_argument("--scanned", type=float, default=0.1)
    args = ap.parse_args(argv)

    rng = random.Random(args.seed)
    out = args.outdir
    (out / "documents").mkdir(parents=True, exist_ok=True)

    results: list[DocResult] = []
    for i in range(args.docs):
        doc_id = f"doc-{i:04d}"
        doc_number = f"WOO-2026-{i + 1:04d}"
        result = build_document(doc_id, doc_number, args.pages, args.scanned, rng)
        (out / "documents" / f"{doc_id}.pdf").write_bytes(result.pdf_bytes)
        results.append(result)

    _write_gold(out / "gold.jsonl", [p for r in results for p in r.gold_pages])
    _write_gold(out / "gold_scanned.jsonl",
               [p for r in results for p in r.gold_scanned_pages])
    _write_queries(out / "queries.tsv", out / "qrels.txt", results)
    _write_manifest(out / "manifest.json", args, results)
    print(f"{len(results)} documents x {args.pages} pages -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
