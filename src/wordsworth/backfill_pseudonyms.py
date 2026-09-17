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
from .models import DocumentText


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="tel wat er geregistreerd zou worden, schrijf niets")
    a = ap.parse_args()

    session_factory = make_session_factory(make_engine())
    documenten = rijen = 0
    with session_factory() as session:
        for row in session.execute(select(DocumentText)).scalars():
            gevonden = pseudonym_registry.tokens_in(row.anonymized_text or "")
            if not gevonden:
                continue
            documenten += 1
            if a.dry_run:
                bestaand = pseudonym_registry.registered(session, row.document_id)
                rijen += len(gevonden - bestaand)
                continue
            rijen += pseudonym_registry.register(
                session, row.document_id, row.anonymized_text or "",
                source=pseudonym_registry.BACKFILLED)
        if not a.dry_run:
            session.commit()

    wat = "zou registreren" if a.dry_run else "geregistreerd"
    print(f"backfill: {rijen} pseudonym(en) {wat}, over {documenten} document(en)")
    if rijen and not a.dry_run:
        print("herkomst: 'backfilled' — afgeleid uit opgeslagen tekst, niet waargenomen"
              " bij het munten")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
