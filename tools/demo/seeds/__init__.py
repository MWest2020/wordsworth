# SPDX-License-Identifier: MIT
"""Seed an empty database, once. One module per concern (`documents`, `topics`,
`grants`), so a later node adds its own seed without editing someone else's."""
from __future__ import annotations

from sqlalchemy import func, select

from wordsworth.audit import current_state
from wordsworth.models import Document, Dossier, GrantRecord, Topic
from wordsworth.states import State

from demo.seeds import documents, grants, topics


def counts(session_factory) -> dict:
    """What the database holds, by the categories the demo promises."""
    with session_factory() as s:
        docs = s.execute(select(Document)).scalars().all()
        states = [current_state(s, d.id) for d in docs]
        return {
            "documents": len(docs),
            "live": sum(1 for st in states if st == State.INDEXED),
            "deleted": sum(1 for st in states if st == State.DELETED),
            "superseded": sum(1 for st in states if st == State.SUPERSEDED),
            "dossiers": s.execute(select(func.count()).select_from(Dossier)).scalar_one(),
            "topics": s.execute(select(func.count()).select_from(Topic)).scalar_one(),
            "grants": s.execute(select(func.count()).select_from(GrantRecord)).scalar_one(),
        }


def seed(stand_ins) -> dict:
    """Seed when the database holds no document; otherwise touch nothing.

    Returns the counts and whether this call seeded. A seed that fails raises
    and leaves what it finished; `serve_local` never serves a database it did
    not seed in the same run, so such a remnant is reset, not resumed."""
    before = counts(stand_ins.session_factory)
    if before["documents"]:
        return {**before, "seeded": False}
    made = documents.seed(stand_ins)
    topics.seed(stand_ins)
    grant_id = grants.seed(stand_ins, made["ids"])
    return {**counts(stand_ins.session_factory), "seeded": True,
            "grant_id": grant_id,
            "grant_document": str(made["ids"][grants.DOCUMENT])}
