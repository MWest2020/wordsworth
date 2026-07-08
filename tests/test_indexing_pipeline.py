import pytest

from wordsworth.pipeline import current_state, process, register
from wordsworth.search_index import InMemoryIndex
from wordsworth.states import State


class _FailingIndex:
    def ensure_ready(self):
        pass

    def index(self, *args, **kwargs):
        raise RuntimeError("search index down")

    def search(self, *args, **kwargs):
        return []


def test_document_is_indexed_and_searchable(session, born_digital_pdf, mem_index,
                                            fake_embedder):
    doc = register(session, "d")
    session.commit()
    final = process(session, doc.id, born_digital_pdf, search_index=mem_index,
                    embedder=fake_embedder)
    session.commit()
    assert final == State.INDEXED
    hits = mem_index.search("born digital document")
    assert any(h.document_id == str(doc.id) for h in hits)


def test_index_outage_is_retryable(session_factory, born_digital_pdf, fake_embedder):
    with session_factory() as s:
        did = register(s, "k").id
        s.commit()
        with pytest.raises(RuntimeError):
            process(s, did, born_digital_pdf, search_index=_FailingIndex(),
                    embedder=fake_embedder)
        s.rollback()
        # Not failed; the run did not commit -> back at the last committed state.
        assert current_state(s, did) == State.REGISTERED

    with session_factory() as s:
        mem = InMemoryIndex()
        assert process(s, did, born_digital_pdf, search_index=mem,
                       embedder=fake_embedder) == State.INDEXED
        s.commit()
        assert mem.search("born digital")
