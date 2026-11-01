# SPDX-License-Identifier: MIT
"""`wordsworth-release-deleted-keys`: the one-off release for documents
deleted before `deleted-document-releases-object-key`.

Deleting a document now releases its `object_key` to the placeholder
`deletion.released_object_key` in the same transaction as the `deleted`
record, so the key is free for the same bytes to be ingested again. A
document deleted before that change still carries its real key; this command
finds those and releases each the same way, appending one `release-key`
audit record per document -- from and to `deleted` (an access/update record,
like `pipeline.reanonymize`: the state does not change, only the key does).

- **Dry run by default.** It lists what it would release and changes nothing.
- **Idempotent.** A document this command already released is not found
  again -- it no longer carries a real key.
- Touches no document that is not, right now, `deleted`.
"""
from __future__ import annotations

import argparse
import json
import sys
from uuid import UUID

from sqlalchemy import select

from . import audit, console_data
from .deletion import DELETED_KEY_PREFIX, released_object_key
from .models import Document
from .states import State


def find_candidates(session) -> list[tuple[UUID, str]]:
    """[(document_id, former_key)] for every document that is, right now,
    `deleted` and still carries a real (not yet released) object key."""
    states = console_data.latest_state_subquery()
    rows = session.execute(
        select(Document.id, Document.object_key)
        .join(states, states.c.document_id == Document.id)
        .where(states.c.to_state == State.DELETED.value,
               ~Document.object_key.like(f"{DELETED_KEY_PREFIX}%"))
    ).all()
    return [(doc_id, key) for doc_id, key in rows]


def release(session, document_id: UUID, former_key: str) -> None:
    doc = session.get(Document, document_id)
    doc.object_key = released_object_key(document_id)
    audit.append(session, document_id=document_id, from_state=State.DELETED.value,
                 to_state=State.DELETED.value, step="release-key",
                 payload={"released_object_key": former_key})


def run(session_factory, *, apply: bool) -> dict:
    with session_factory() as session:
        candidates = find_candidates(session)
    report: dict = {"found": [str(doc_id) for doc_id, _ in candidates], "applied": False}
    if not apply:
        return report

    released = []
    for document_id, former_key in candidates:
        with session_factory() as session:
            release(session, document_id, former_key)
            session.commit()
        released.append(str(document_id))
    report.update(applied=True, released=released)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="wordsworth-release-deleted-keys",
                                 description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true",
                    help="actually release the keys; without it, list only")
    args = ap.parse_args(argv)

    from .db import make_engine, make_session_factory
    report = run(make_session_factory(make_engine()), apply=args.apply)
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
