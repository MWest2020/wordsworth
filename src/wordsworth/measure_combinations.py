# SPDX-License-Identifier: MIT
"""Count the documents in which a declared combination occurs.

Measure before claiming. Without this number, any statement about quasi-
identifiers in a corpus is a guess, and the whole point of the change is to stop
guessing about exactly this.

The measurement reads the tokens the pipeline minted per document
(``document_pseudonyms``), not the source text. That is deliberate: those tokens
are the artefact this system actually produced, on the text it actually saw, so
the count says what the pipeline did rather than what a re-run of the detectors
would say today.

It follows that the measurement can only see types the pipeline labels. A
combination naming a type no detector emits — ``GENDER`` is the obvious one —
can never be complete in any document, and the report says so by name instead of
reporting a comforting zero.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict

from sqlalchemy import select

from . import combinations as _combinations
from .models import DocumentPseudonym
from .pseudonymizer import label_of


def labels_by_document(session) -> dict:
    """``document_id -> {LABEL, ...}`` from the registered pseudonyms."""
    out: dict = defaultdict(set)
    for doc_id, token in session.execute(
            select(DocumentPseudonym.document_id, DocumentPseudonym.pseudonym)):
        out[doc_id].add(label_of(token))
    return out


def measure(session, declarations: list[dict]) -> list[dict]:
    """Per declared combination: in how many documents every type occurs."""
    declared = _combinations.parse(declarations)
    per_doc = labels_by_document(session)
    seen = {lbl for labels in per_doc.values() for lbl in labels}
    report = []
    for c in declared:
        types = {t.upper() for t in c.types}
        report.append({
            "types": sorted(types),
            "reason": c.reason,
            "documents": sum(1 for labels in per_doc.values() if types <= labels),
            # A type the corpus never carries makes the count meaningless rather
            # than low; naming it is the difference between "does not occur" and
            # "cannot be seen".
            "unobservable_types": sorted(types - seen),
        })
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="wordsworth-measure-combinations",
        description="Count documents carrying every type of a declared combination")
    ap.add_argument("declarations", help="JSON file: a profile, or a bare list of "
                                         "{types, reason} declarations")
    args = ap.parse_args(argv)

    from .db import make_engine, make_session_factory

    raw = json.loads(open(args.declarations, encoding="utf-8").read())
    decls = raw.get("combinations", []) if isinstance(raw, dict) else raw
    if not decls:
        print("no combinations declared", file=sys.stderr)
        return 2
    with make_session_factory(make_engine())() as session:
        report = measure(session, decls)
    total = len(report)
    for r in report:
        note = (f"  [unobservable: {', '.join(r['unobservable_types'])}]"
                if r["unobservable_types"] else "")
        print(f"{r['documents']:>6}  {' + '.join(r['types'])}{note}")
    print(f"{total} combination(s) measured", file=sys.stderr)
    return 0


if __name__ == "__main__":     # pragma: no cover
    raise SystemExit(main())
