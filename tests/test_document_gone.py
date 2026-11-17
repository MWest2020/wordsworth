# SPDX-License-Identifier: MIT
"""document_gone.check: unknown (404), deleted (410), else the state
(deleted-document-answers-410, design.md decision 4). Reads
`pipeline.current_state` and nothing else, so each state is set directly on
the audit chain rather than through the full pipeline."""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException

from wordsworth import audit, document_gone
from wordsworth.models import Document
from wordsworth.states import State

LIVE_STATES = [s for s in State if s != State.DELETED]


def _doc(session):
    doc = Document(object_key="k")
    session.add(doc)
    session.flush()
    return doc.id


def test_unknown_document_is_404(session):
    with pytest.raises(HTTPException) as exc:
        document_gone.check(session, uuid4())
    assert exc.value.status_code == 404
    assert exc.value.detail == "unknown document"


def test_deleted_document_is_410(session):
    did = _doc(session)
    audit.append(session, document_id=did, from_state="indexed",
                to_state="deleted", step="delete")
    session.commit()
    with pytest.raises(HTTPException) as exc:
        document_gone.check(session, did)
    assert exc.value.status_code == 410
    assert exc.value.detail == "document deleted"


@pytest.mark.parametrize("state", LIVE_STATES, ids=lambda s: s.value)
def test_each_live_state_returns_the_state(session, state):
    did = _doc(session)
    audit.append(session, document_id=did, from_state=None,
                to_state=state.value, step="x")
    session.commit()
    assert document_gone.check(session, did) == state
