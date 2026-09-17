# SPDX-License-Identifier: MIT
"""Which pseudonyms belong to which document.

The mapping store is global — lookup by pseudonym, not by document — because one
value must yield one token everywhere, or pseudonymised text stops being
searchable. The cost of that choice is that a reveal resolves any token it meets,
whoever minted it.

`neutralise_foreign_tokens` closes the entrance an attacker can walk today: a
token already present in supplied text is taken apart before anonymisation. This
module closes the exit, which is the cheaper thing to guard — there is one reveal
path and an unbounded number of ways text can enter a system.

That guard is also what makes registration honest. Because foreign tokens are
defused *before* an anonymisation run, every token in that run's output was
minted by it. "Present in the result" and "minted here" are the same set, so the
registry can be read off the text instead of threaded through the anonymiser.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import DocumentPseudonym

MINTED = "minted"
BACKFILLED = "backfilled"

# Same shape as the pseudonymiser's token; duplicated deliberately rather than
# imported, so this module does not depend on the anonymisation layer it guards.
_TOKEN = re.compile(r"\[[A-Z0-9_]+:[0-9a-f]{8}\]")


def tokens_in(text: str) -> set[str]:
    """Every pseudonym appearing in ``text``."""
    return set(_TOKEN.findall(text or ""))


def register(session: Session, document_id: UUID, text: str,
             source: str = MINTED) -> int:
    """Register the pseudonyms in ``text`` for ``document_id``. Idempotent.

    Returns the number of rows added. Re-anonymising a document adds the new
    tokens; it does not remove old ones, because an older reveal of the same
    document may still be in flight and a registry that shrinks under a running
    request is a race, not a safeguard.
    """
    gevonden = tokens_in(text)
    if not gevonden:
        return 0
    bestaand = set(session.execute(
        select(DocumentPseudonym.pseudonym).where(
            DocumentPseudonym.document_id == document_id,
            DocumentPseudonym.pseudonym.in_(gevonden),
        )
    ).scalars())
    nieuw = gevonden - bestaand
    now = datetime.now(timezone.utc)
    for pseudonym in sorted(nieuw):
        session.add(DocumentPseudonym(document_id=document_id, pseudonym=pseudonym,
                                      source=source, created_at=now))
    return len(nieuw)


def registered(session: Session, document_id: UUID) -> set[str]:
    """The pseudonyms registered for this document."""
    return set(session.execute(
        select(DocumentPseudonym.pseudonym).where(
            DocumentPseudonym.document_id == document_id
        )
    ).scalars())
