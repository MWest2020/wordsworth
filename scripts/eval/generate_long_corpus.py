# SPDX-License-Identifier: MIT
"""Generate a long synthetic PDF corpus with page-level ground truth
(synthetic-long-corpus).

Real Woo publications are long PDFs with page boundaries, long-document
ranking and pages without a text layer -- what the short-text corpus
(`generate_ground_truth.py`) cannot test. This writes, from one generation:

  documents/<doc-id>.pdf  born-digital PDFs of ``--pages`` pages, with a
                          header/footer on every page ("pagina x van y", a
                          `WOO-<year>-<4 digits>` document number) and the
                          word SYNTHETISCH
  gold.jsonl              one line per born-digital page, in
                          `wordsworth.eval.pii`'s `load_gold` format
  gold_scanned.jsonl      the same for scanned pages (no text layer), kept
                          apart -- NOT part of the score to quote: `pii_run`
                          detects over gold text and never opens a PDF
  queries.tsv / qrels.txt one query per document, answered only by a phrase
                          planted at or after page 20 (or the last page)
  manifest.json           seed, options, per-type counts, the scanned pages
                          per document, the queries, and the synthetic caveat

Read the caveat in the manifest before quoting any score: this text was
written by us and is more regular than administrative reality.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from wordsworth.eval.long_corpus import LongDocument, build_document
from wordsworth.eval.long_corpus_pdf import write_pdf


def _page_record(page_no: int, doc_id: str, page) -> dict:
    return {"id": page.doc_id, "doc": doc_id, "page": page_no,
            "text": page.text, "entities": page.entities}


def _counts_per_type(records: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in records:
        for e in r["entities"]:
            counts[e["type"]] = counts.get(e["type"], 0) + 1
    return dict(sorted(counts.items()))


def generate(outdir: Path, docs: int, pages: int, seed: int, scanned: float) -> list[LongDocument]:
    rng = random.Random(seed)
    long_docs = [build_document(f"doc-{i:04d}", rng, pages, scanned) for i in range(docs)]

    (outdir / "documents").mkdir(parents=True, exist_ok=True)
    gold: list[dict] = []
    gold_scanned: list[dict] = []
    for ld in long_docs:
        pdf_bytes = write_pdf(ld.pages, ld.scanned)
        (outdir / "documents" / f"{ld.doc_id}.pdf").write_bytes(pdf_bytes)
        for page_no, page in enumerate(ld.pages, start=1):
            record = _page_record(page_no, ld.doc_id, page)
            (gold_scanned if page_no in ld.scanned else gold).append(record)

    (outdir / "gold.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in gold), encoding="utf-8")
    (outdir / "gold_scanned.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in gold_scanned),
        encoding="utf-8")
    (outdir / "queries.tsv").write_text(
        "".join(f"q-{ld.doc_id}\t{ld.query_text}\n" for ld in long_docs), encoding="utf-8")
    # Every document is judged for every query -- a document missing from
    # qrels is indistinguishable from one judged irrelevant.
    (outdir / "qrels.txt").write_text(
        "".join(f"q-{ld.doc_id} 0 {other.doc_id} {1 if other.doc_id == ld.doc_id else 0}\n"
                for ld in long_docs for other in long_docs), encoding="utf-8")
    (outdir / "manifest.json").write_text(json.dumps({
        "seed": seed,
        "options": {"docs": docs, "pages": pages, "scanned": scanned},
        "documents": len(long_docs),
        "pages_per_document": pages,
        "gold_pages": len(gold),
        "gold_scanned_pages": len(gold_scanned),
        "entities_per_type": _counts_per_type(gold),
        "entities_per_type_scanned": _counts_per_type(gold_scanned),
        "scanned_pages_per_document": {ld.doc_id: sorted(ld.scanned) for ld in long_docs},
        "queries": [{"query_id": f"q-{ld.doc_id}", "doc_id": ld.doc_id,
                     "answer_page": ld.answer_page, "answer_phrase": ld.answer_phrase}
                    for ld in long_docs],
        "caveat": ("Synthetic. Written by us and more regular than administrative "
                   "reality: a score here is a lower bound for the machinery, not a "
                   "prediction for production text. gold_scanned.jsonl is not part of "
                   "the score to quote -- pii_run detects over gold text and never "
                   "opens a PDF, so scoring it would count pages the pipeline cannot "
                   "see as if extraction were perfect."),
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return long_docs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Generate a long synthetic PDF corpus")
    ap.add_argument("outdir", type=Path)
    ap.add_argument("--docs", type=int, default=30)
    ap.add_argument("--pages", type=int, default=30)
    ap.add_argument("--seed", type=int, default=20261106)
    ap.add_argument("--scanned", type=float, default=0.1)
    args = ap.parse_args(argv)

    long_docs = generate(args.outdir, args.docs, args.pages, args.seed, args.scanned)
    print(f"{len(long_docs)} documents x {args.pages} pages -> {args.outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
