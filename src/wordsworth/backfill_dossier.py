# SPDX-License-Identifier: MIT
"""Give documents from before dossiers existed a place to be found (dossier-scope).

A scoped search answers only from the dossiers in scope. Documents that belong to
none are therefore invisible — and every document ingested before this change
belongs to none. A scope that makes the existing corpus unfindable is not a
migration but a loss.

The name has to say where they came from rather than pretend they were always a
case, because they were not: they arrived as one corpus, in one go, and that is
the honest thing to call them.
"""
from __future__ import annotations

import argparse
import sys
from uuid import uuid4

from sqlalchemy import select

from . import dossiers
from .db import make_engine, make_session_factory
from .models import Document, DossierDocument
from .pipeline import dossiers_of, get_anonymized_text


def orphans(session) -> list[Document]:
    """Documents that are in no dossier at all.

    Live ones only: a superseded copy left its dossiers on purpose, and its
    survivor holds them (one-document-per-object).
    """
    member = select(DossierDocument.document_id)
    return list(session.execute(
        select(Document).where(Document.id.not_in(member),
                               Document.superseded_by.is_(None))).scalars())


def adopt(session, name: str, index=None, *, actor: str = "backfill") -> dict:
    """Put every dossier-less document into the named dossier, and tell the index.

    The index has to learn it here. It holds the dossiers per document, so a
    membership the index does not know about is a document a scoped search still
    cannot reach — and then this command would not have done the one thing it
    exists for. Without an index the memberships are still written, and the
    caller is told that a reindex is outstanding.
    """
    found = orphans(session)
    if not found:
        return {"dossier": name, "adopted": 0, "already_placed": True,
                "reindexed": 0, "without_text": 0, "niet_geindexeerd": 0}
    dossier = dossiers.ensure(session, name)
    # One batch id for the whole run. The records are honest per document --
    # every one really did get a membership -- but without something tying them
    # together a day of history reads as hundreds of unrelated decisions instead
    # of the single command it was.
    batch = uuid4().hex[:12]
    added = [d for d in found
             if dossiers.add(session, dossier.id, d.id, actor=actor, batch=batch)]
    reindexed = without_text = niet_geindexeerd = 0
    for doc in added if index is not None else []:
        if get_anonymized_text(session, doc.id) is None:
            # Never indexed in the first place (never got through the straat),
            # so there is nothing to update and nothing was lost.
            without_text += 1
            continue
        # Only the dossiers. An earlier version wrote the whole document back
        # and dropped every embedding in the corpus doing it.
        if index.set_dossiers(str(doc.id), dossiers_of(session, doc.id)):
            reindexed += 1
        else:
            niet_geindexeerd += 1
    return {"dossier": name, "adopted": len(added), "already_placed": False,
            "reindexed": reindexed, "without_text": without_text,
            "niet_geindexeerd": niet_geindexeerd}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="wordsworth-backfill-dossier",
        description="Place documents that predate dossiers into one named dossier")
    ap.add_argument("name", help="e.g. 'corpus-2026-09' — say where they came "
                                 "from, do not pretend they were a case")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-index", action="store_true",
                    help="skip updating the search index (a reindex stays due)")
    args = ap.parse_args(argv)

    index = None
    if not args.no_index:
        if args.dry_run:
            # A dry run must not write. The database can be rolled back; the
            # index cannot, so touching it would make "dry" a lie — and it did:
            # the first dry run against production wrote 770 documents.
            print("droge run: de index wordt NIET aangeraakt", file=sys.stderr)
        else:
            from .opensearch_index import OpenSearchIndex
            index = OpenSearchIndex.from_config()
            index.ensure_ready()
    with make_session_factory(make_engine())() as session:
        stats = adopt(session, args.name, index)
        if args.dry_run:
            session.rollback()
        else:
            session.commit()
    verb = "zou plaatsen" if args.dry_run else "geplaatst"
    print(f"{verb}: {stats['adopted']} document(en) in dossier {stats['dossier']!r}")
    if stats["already_placed"]:
        print("  elk document zat al in een dossier")
    else:
        print(f"  index bijgewerkt       : {stats['reindexed']}")
        print(f"  zonder opgeslagen tekst: {stats['without_text']} "
              f"(stond nooit in de index)")
        if stats.get("niet_geindexeerd"):
            print(f"  wel tekst, niet in de index: {stats['niet_geindexeerd']} "
                  f"(die zijn ook zonder dossier onvindbaar)")
        if args.no_index or args.dry_run:
            print("  LET OP: de index is niet bijgewerkt; tot een herindexering "
                  "vindt een gescopete zoekopdracht deze documenten niet")
    return 0


if __name__ == "__main__":     # pragma: no cover
    raise SystemExit(main())
