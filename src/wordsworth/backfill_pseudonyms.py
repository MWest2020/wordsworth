# SPDX-License-Identifier: MIT
"""Fill the per-document pseudonym registry from already-stored text.

`pseudonyms-per-document` gates a reveal on a registry that is written by every
anonymisation run. Documents anonymised before that change have no rows, and a
document with no rows reveals nothing — fail-closed, which is the right default
and the wrong thing to discover in production.

This command closes that gap once. It is idempotent and safe to re-run.

**What it can and cannot know.** It reads the stored text and registers the
tokens it finds, so every row it writes is marked `backfilled` rather than
`minted`. A backfill cannot tell whether a token was minted for that document or
arrived there before `neutralise_foreign_tokens` existed. Recording that
uncertainty is cheaper than arguing about it later: whoever investigates an
incident sees which rows were derived and which were observed.

    wordsworth-backfill-pseudonyms            # doet het werk
    wordsworth-backfill-pseudonyms --dry-run  # telt alleen
"""
from __future__ import annotations

import argparse

from sqlalchemy import select

from . import pseudonym_registry
from .db import make_engine, make_session_factory
from .ingest_lock import lock_for_process
from .models import DocumentText


def run(session_factory, *, dry_run: bool) -> tuple[int, int]:
    """(documents with tokens, rows registered or that would be).

    One transaction per document, through `pseudonym_registry.link` (#465):
    the document's row locked FOR SHARE first, its text read again under
    that lock -- a deletion that committed in between took the text with it,
    and nothing is registered for a deleted document -- then the link under
    the audit chain lock, which is released at each commit
    (`docs/reference/lock-order.md`). A dry run locks nothing."""
    with session_factory() as session:
        ids = session.execute(select(DocumentText.document_id)
                              .order_by(DocumentText.document_id)).scalars().all()
    documenten = rijen = 0
    for document_id in ids:
        with session_factory() as session:
            if not dry_run:
                lock_for_process(session, document_id)
            row = session.get(DocumentText, document_id, populate_existing=True)
            tekst = (row.anonymized_text or "") if row is not None else ""
            gevonden = pseudonym_registry.tokens_in(tekst)
            if not gevonden:
                continue
            documenten += 1
            if dry_run:
                bestaand = pseudonym_registry.registered(session, document_id)
                rijen += len(gevonden - bestaand)
                continue
            rijen += pseudonym_registry.link(
                session, document_id, tekst, source=pseudonym_registry.BACKFILLED)
            session.commit()
    return documenten, rijen


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="tel wat er geregistreerd zou worden, schrijf niets")
    a = ap.parse_args()

    documenten, rijen = run(make_session_factory(make_engine()), dry_run=a.dry_run)

    wat = "zou registreren" if a.dry_run else "geregistreerd"
    print(f"backfill: {rijen} pseudonym(en) {wat}, over {documenten} document(en)")
    if rijen and not a.dry_run:
        print("herkomst: 'backfilled' — afgeleid uit opgeslagen tekst, niet waargenomen"
              " bij het munten")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
