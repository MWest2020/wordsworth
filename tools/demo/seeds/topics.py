# SPDX-License-Identifier: MIT
"""Compute the demo dossier's topics with the same function the API calls."""
from __future__ import annotations

from sqlalchemy import select

from wordsworth import topics
from wordsworth.models import Dossier

from demo import corpus


def seed(stand_ins) -> int:
    """Cluster the dossier as `POST /dossiers/{name}/topics` would; returns how
    many topics came out. Zero is an error: the topic page is part of the demo."""
    with stand_ins.session_factory() as s:
        dossier = s.execute(select(Dossier).where(
            Dossier.name == corpus.DOSSIER)).scalar_one()
        made = topics.compute(s, stand_ins.index, dossier.id)
        s.commit()
        if not made.topics:
            raise RuntimeError(f"no topics in {corpus.DOSSIER!r} "
                               f"({made.seen} documents seen)")
        return len(made.topics)
