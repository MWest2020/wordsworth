# SPDX-License-Identifier: MIT
"""The count-only check of a re-anonymisation (reanonymise-particle-name-documents).

After a detection change -- a new rule, a gazetteer entry -- documents are
re-anonymised through `reprocess.one`. This module says, per document and per
type, how many distinct pseudonyms its stored text held before and after, and
how many were added and removed. Nothing else: never a value, never a token,
never the text around it, never an offset. The numbers are what an operator
may read in a log and in the answer of `POST /reprocess`; the text is not.

Counted from the STORED pseudonymised text, not from the pseudonym registry:
`pseudonym_registry.register` never removes a token, so a registry count can
only grow and would report tokens the text no longer holds.

Distinct pseudonyms, not occurrences: one person named five times is one.
And added/removed next to the totals, because the case this exists for -- a
first name that was a token of its own becoming one token for the whole name
with its particle -- leaves the total equal (before 4, after 4) while one
token was replaced (added 1, removed 1).

Here and not in `reprocess.py`, which stays the loop and gets the calls only.
"""
from __future__ import annotations

import json
import logging
from collections import Counter
from uuid import UUID

from sqlalchemy.orm import Session

from .models import DocumentText
from .pseudonym_registry import tokens_in
from .pseudonymizer import label_of
from .structured_log import logger

#: The four numbers per type, in the order the log line and the answer use.
FIELDS = ("before", "after", "added", "removed")


def compare(before_text: str, after_text: str) -> dict[str, dict[str, int]]:
    """Per type: distinct pseudonyms in ``before_text`` and ``after_text``, and
    how many are in after and not in before (added) and the reverse (removed).

    Pure. Only the types that occur in either text are present. The returned
    dict holds type names and numbers, never a token.
    """
    before, after = tokens_in(before_text), tokens_in(after_text)
    added, removed = after - before, before - after
    tellers = {naam: Counter(label_of(t) for t in tokens)
               for naam, tokens in (("before", before), ("after", after),
                                    ("added", added), ("removed", removed))}
    types = sorted(set(tellers["before"]) | set(tellers["after"]))
    return {t: {f: tellers[f][t] for f in FIELDS} for t in types}


def stored_text(session: Session, document_id: UUID) -> str:
    """The pseudonymised text stored for this document, as the reader sees it.

    A document without a stored text holds no pseudonyms, so it counts as the
    empty text: that is what is stored, not a guess. `reprocess.one` only gets
    here for ANONYMIZED/INDEXED documents, which have one.
    """
    row = session.get(DocumentText, document_id)
    return row.anonymized_text if row is not None else ""


def log(document_id: UUID | str, counts: dict[str, dict[str, int]]) -> str:
    """Emit and return one JSON line with the document id and its counts.

    Through the `wordsworth.pipeline` logger, because `configure_logging` is
    what production turns on (a logger of its own stays at WARNING and prints
    nothing, see `structured_log.log_topic_label`). Only the id, type names and
    numbers go in; the caller logs after `session.commit()` has returned, so a
    rolled-back run never reports a change.
    """
    line = json.dumps(
        {
            "event": "reprocess_counts",
            "document_id": str(document_id),
            "counts": {t: {f: int(c[f]) for f in FIELDS}
                       for t, c in sorted(counts.items())},
            "level": "info",
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    logger.log(logging.INFO, line)
    return line
