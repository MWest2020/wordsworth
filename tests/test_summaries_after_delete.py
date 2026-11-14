# SPDX-License-Identifier: MIT
"""#455 review: once deletion removes a document's summary, the summaries
command must not pick the deleted document up again (`--ontbrekend` counted it
as `without_text` and the CronJob exited 1 after every deletion), and a
summary made while the document is being deleted must not be stored."""
from __future__ import annotations

from uuid import uuid4

from wordsworth import samenvatten, summaries
from wordsworth.audit import current_state
from wordsworth.deletion import delete_document
from wordsworth.models import DocumentSummary, DocumentText
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.pipeline import register
from wordsworth.search_index import InMemoryIndex
from wordsworth.states import State

TEXT = "De aanvraag voor een dakkapel is afgewezen."


class _Keep:
    """A session that outlives `with`, so the command uses the test's session."""

    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, *a):
        return False


class _Model:
    def __init__(self):
        self.calls: list[str] = []

    def generate(self, query, sources):        # pragma: no cover - not used
        raise AssertionError("summarise, not generate")

    def summarise(self, text: str) -> str:
        self.calls.append(text)
        return "Het besluit gaat over een dakkapel."


def _doc(session, text=TEXT):
    doc = register(session, f"documents/{uuid4().hex}")
    session.merge(DocumentText(document_id=doc.id, anonymized_text=text))
    session.flush()
    return doc


def _delete(session, document_id):
    delete_document(session, document_id, InMemoryObjectStore(), InMemoryIndex(),
                    actor="tester")


def test_ontbrekend_skips_a_deleted_document_and_exits_0(session, monkeypatch, capsys):
    deleted, live = _doc(session), _doc(session, "Een besluit over een hek.")
    session.commit()
    assert summaries.for_document(session, _Model(), deleted.id, "test") is not None
    session.commit()
    _delete(session, deleted.id)              # removes its text and its summary
    session.commit()

    model = _Model()
    monkeypatch.setattr(samenvatten, "make_engine", lambda: None)
    monkeypatch.setattr(samenvatten, "make_session_factory",
                        lambda e: (lambda: _Keep(session)))
    monkeypatch.setattr(samenvatten.OllamaGenerator, "from_config",
                        classmethod(lambda cls: model))

    code = samenvatten.main(["--ontbrekend"])

    out = capsys.readouterr().out
    assert code == 0, out
    assert "seen=1" in out and "made=1" in out and "without_text=0" in out
    assert model.calls == ["Een besluit over een hek."]
    assert session.get(DocumentSummary, deleted.id) is None
    assert session.get(DocumentSummary, live.id) is not None
    assert current_state(session, deleted.id) == State.DELETED


def test_a_summary_made_while_the_document_is_deleted_is_not_stored(session_factory):
    """The deletion commits between reading the text and storing the summary
    (the model takes minutes): the store finds no text and writes nothing."""

    class _DeletesWhileSummarising(_Model):
        def summarise(self, text: str) -> str:
            with session_factory() as other:
                _delete(other, doc_id)
                other.commit()
            return super().summarise(text)

    with session_factory() as s:
        doc_id = _doc(s).id
        s.commit()
        model = _DeletesWhileSummarising()

        assert summaries.for_document(s, model, doc_id, "test") is None
        s.commit()

        assert model.calls == [TEXT]          # the model did run, on the old text
    with session_factory() as s:
        assert s.get(DocumentSummary, doc_id) is None
        assert current_state(s, doc_id) == State.DELETED


def test_a_summary_is_still_stored_while_the_text_is_there(session_factory):
    """The guard does not stop the ordinary case, nor the upsert over an
    existing summary."""
    with session_factory() as s:
        doc_id = _doc(s).id
        s.commit()
        first = summaries.for_document(s, _Model(), doc_id, "eerste")
        s.commit()
        again = summaries.for_document(s, _Model(), doc_id, "tweede")
        s.commit()
        assert first is not None and again is not None
    with session_factory() as s:
        assert s.get(DocumentSummary, doc_id).model == "tweede"
