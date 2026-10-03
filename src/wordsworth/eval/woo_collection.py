# SPDX-License-Identifier: MIT
"""A ranking collection derived from what the Woo publisher recorded.

No qrels exist for the Woo corpus, and judging relevance is a person's work
(`docs/reference/evaluation.md`). Two sets can be derived without anyone
judging (change `long-documents-rank-fairly`, design Decision 1):

- **known-item:** a document's file name is its publisher's label for it, and
  stripped of ids and mail prefixes it is a query whose one relevant document
  is that document;
- **per decision:** `herkomst.jsonl` records each document's Woo decision page;
  the decision's title is a query, its documents are the relevant set.

Bias, said here as well as in the design: title-word queries favour keyword
matching. Fair between two rankers fed the same queries; a weaker claim for a
ranker that leans on BM25.

The rules are functions so they are tested, not tuned per case.
"""
from __future__ import annotations

import json
import re
import statistics
from collections import defaultdict
from pathlib import Path

from sqlalchemy import func, select

from ..models import Document, DocumentText
from .metrics import ndcg_at_k, recall_at_k

#: Tokens in a file name that are not about the subject: mail prefixes, file
#: types, and the publisher's own markers.
NOISE = frozenset({"re", "fw", "fwd", "vs", "vg", "msg", "pdf", "jpg", "jpeg",
                   "png", "doc", "docx", "xlsx", "image", "img", "prdf", "def"})


def query_from_filename(name: str) -> str | None:
    """Subject words of a file name, or None when it has fewer than two.

    `RE_WP_Echteld_Lienden_Verweerschrift_natuur_PRDF_11025011_2_msg_44684629_ff4556354c.pdf`
    -> "echteld lienden verweerschrift natuur". Numbers, hex ids, words under
    three letters and the NOISE list go; what remains is the subject.
    """
    stem = re.sub(r"\.pdf$", "", name, flags=re.IGNORECASE)
    words = []
    for tok in re.split(r"[_\W]+", stem):
        low = tok.lower()
        if (len(low) < 3 or low in NOISE or low.isdigit()
                or re.fullmatch(r"[0-9a-f]{8,}", low)
                or not re.search(r"[a-z]", low)):
            continue
        words.append(low)
    return " ".join(words) if len(words) >= 2 else None


def query_from_decision(url: str) -> str:
    """`.../woo-besluit-over-ballonfiesta-barneveld2026-009291` ->
    "woo besluit over ballonfiesta barneveld"."""
    slug = url.rstrip("/").rsplit("/", 1)[-1]
    slug = re.sub(r"\d{4}-\d+$", "", slug)
    return " ".join(w for w in slug.split("-") if w)


def thirds(lengths: dict[str, int]) -> dict[str, str]:
    """Each id -> "short" | "middle" | "long", by equal-count thirds of length.

    Ties broken by id so the split is the same on every run.
    """
    order = sorted(lengths, key=lambda i: (lengths[i], i))
    n = len(order)
    cut1, cut2 = n // 3, (2 * n) // 3
    return {i: ("short" if r < cut1 else "middle" if r < cut2 else "long")
            for r, i in enumerate(order)}


def reciprocal_rank(ranked: list[str], relevant: set[str]) -> float:
    """1 / rank of the first relevant id, 0.0 if none is ranked."""
    for r, doc_id in enumerate(ranked, start=1):
        if doc_id in relevant:
            return 1.0 / r
    return 0.0


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
