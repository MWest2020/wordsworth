import pytest
from sqlalchemy import func, select

from wordsworth.models import Document
from wordsworth.pipeline import current_state, process, register, transition
from wordsworth.states import State


def test_register_sets_registered(session):
    doc = register(session, "k")
    session.commit()
    assert current_state(session, doc.id) == State.REGISTERED


def test_illegal_transition_raises(session):
    doc = register(session, "k")
    session.commit()
    with pytest.raises(ValueError):
        transition(session, doc.id, State.INDEXED, step="skip")


def test_transition_to_same_state_is_noop(session):
    doc = register(session, "k")
    session.commit()
    assert transition(session, doc.id, State.REGISTERED, step="register") is None


def test_atomic_no_partial_persist(session_factory):
    # A failure before commit must leave neither the document nor an audit record.
    with pytest.raises(RuntimeError):
        with session_factory() as s:
            register(s, "k")
            raise RuntimeError("boom before commit")
    with session_factory() as s:
        count = s.execute(select(func.count()).select_from(Document)).scalar_one()
        assert count == 0


def test_process_resumes_from_current_state(session, born_digital_pdf, mem_index,
                                            fake_embedder):
    doc = register(session, "k")
    # Simulate a prior partial run that already profiled the document.
    transition(session, doc.id, State.EXTRACTABLE, step="profile",
               payload={"chars": 50, "pages": 1, "bytes": 10})
    session.commit()
    # Resume: text is re-derived from the source PDF (no clear-text store).
    final = process(session, doc.id, born_digital_pdf, search_index=mem_index,
                    embedder=fake_embedder)
    session.commit()
    assert final == State.INDEXED
    assert current_state(session, doc.id) == State.INDEXED
