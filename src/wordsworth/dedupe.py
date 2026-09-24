# SPDX-License-Identifier: MIT
"""`wordsworth-dedupe`: retire every copy of an object that already is a document.

One-time cleanup for one-document-per-object. Measured 2026-09-24: 173 copies
over 93 objects, 173 of their dossier memberships, 159 search-index entries.

- **Dry run by default.** It prints what it would do and changes nothing.
- **`--apply` needs the numbers you expect**, and stops before touching
  anything if the database says otherwise. A cleanup that finds more than it
  was sent for is finding something nobody has looked at.
- **The oldest registered copy survives** (design, Decision 4).
- **One transaction per object**, not one for the lot: a long transaction on
  `documents` is what blocked three deploys in September.
- Index entries can only be counted by removing them, so that number is checked
  after the run; a difference is reported and the exit code says so.
"""
from __future__ import annotations

import argparse
import json
import sys
from uuid import uuid4

from sqlalchemy import func, select

from .models import AuditRecord, Document, DossierDocument
from .pipeline import dossiers_of
from .supersession import supersede

ACTOR = "dedupe"


def plan(session) -> list[tuple[str, object, list]]:
    """[(object_key, survivor_id, [copy_ids])] for every object with copies."""
    registered = (select(AuditRecord.document_id, func.min(AuditRecord.seq).label("seq"))
                  .where(AuditRecord.step == "register")
                  .group_by(AuditRecord.document_id).subquery())
    rows = session.execute(
        select(Document.object_key, Document.id)
        .join(registered, registered.c.document_id == Document.id, isouter=True)
        .where(Document.superseded_by.is_(None))
        .order_by(Document.object_key, registered.c.seq.nullslast(), Document.id)).all()
    groups: dict[str, list] = {}
    for key, doc_id in rows:
        groups.setdefault(key, []).append(doc_id)
    return [(key, ids[0], ids[1:]) for key, ids in groups.items() if len(ids) > 1]


def counts(session, groups) -> dict[str, int]:
    copies = [c for _, _, cs in groups for c in cs]
    memberships = session.execute(
        select(func.count()).select_from(DossierDocument)
        .where(DossierDocument.document_id.in_(copies))).scalar_one() if copies else 0
    return {"objects": len(groups), "copies": len(copies), "memberships": memberships}


def run(session_factory, index, *, apply: bool, expect: dict[str, int | None]) -> dict:
    with session_factory() as session:
        groups = plan(session)
        found = counts(session, groups)
    report = {"found": found, "applied": False}
    wrong = {k: {"expected": v, "found": found[k]} for k, v in expect.items()
             if k in found and v is not None and v != found[k]}
    if wrong:
        report["refused"] = wrong
        return report
    if not apply:
        return report

    batch = f"dedupe-{uuid4().hex[:8]}"
    done = {"superseded": 0, "moved": 0, "removed": 0, "index_entries": 0}
    for _key, survivor, copies in groups:
        with session_factory() as session:
            outcomes = [supersede(session, c, survivor, actor=ACTOR, batch=batch,
                                  index=index) for c in copies]
            session.commit()
            moved = sum(o["moved"] for o in outcomes)
            if moved and index is not None:
                index.set_dossiers(str(survivor), dossiers_of(session, survivor))
        done["superseded"] += sum(o["superseded"] for o in outcomes)
        done["moved"] += moved
        done["removed"] += sum(o["removed"] for o in outcomes)
        done["index_entries"] += sum(o["index_entry"] for o in outcomes)
    report.update(applied=True, batch=batch, done=done)
    want = expect.get("index_entries")
    if want is not None and want != done["index_entries"]:
        report["index_entries_differ"] = {"expected": want,
                                          "removed": done["index_entries"]}
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="wordsworth-dedupe", description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true", help="actually retire the copies")
    ap.add_argument("--expect-copies", type=int)
    ap.add_argument("--expect-memberships", type=int)
    ap.add_argument("--expect-index-entries", type=int)
    args = ap.parse_args(argv)
    if args.apply and (args.expect_copies is None or args.expect_memberships is None):
        ap.error("--apply needs --expect-copies and --expect-memberships")

    from .db import make_engine, make_session_factory
    from .opensearch_index import OpenSearchIndex
    report = run(make_session_factory(make_engine()), OpenSearchIndex.from_config(),
                 apply=args.apply,
                 expect={"copies": args.expect_copies,
                         "memberships": args.expect_memberships,
                         "index_entries": args.expect_index_entries})
    print(json.dumps(report, indent=2, default=str))
    return 1 if ("refused" in report or "index_entries_differ" in report) else 0


if __name__ == "__main__":
    sys.exit(main())
