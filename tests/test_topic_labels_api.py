# SPDX-License-Identifier: MIT
"""`POST /topics/{topic_id}/label` (topic-labels-llm): één onderwerp per
aanroep, achter de corpus-leespoort, en een 503 die zegt wat er weg is."""
from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from topic_label_setup import GOED, Kapot, Model, dossier
from wordsworth.api import create_app
from wordsworth.models import Topic
from wordsworth.search_index import InMemoryIndex, SearchUnavailable

MARK, GAST = {"x-api-key": "k-mark"}, {"x-api-key": "k-gast"}


def _app(session_factory, index, generator):
    return TestClient(create_app(
        session_factory=session_factory, search_index=index, generator=generator,
        api_keys={"k-mark": "mark", "k-gast": "gast"},
        corpus_read_labels=["mark"]))


def _twee(session_factory, index, samenvatting="Een kapvergunning."):
    with session_factory() as s:
        _, topics, _ = dossier(s, index, topics=[
            ("kap · boom", [([1.0, 0.0], samenvatting)] * 2),
            ("geluid · evenement", [([0.0, 1.0], samenvatting)] * 2)])
        return [t.id for t in topics]


def test_one_topic_is_labelled_and_no_other_changes(session_factory):
    index = InMemoryIndex()
    eerste, tweede = _twee(session_factory, index)
    model = Model()

    r = _app(session_factory, index, model).post(f"/topics/{eerste}/label",
                                                 headers=MARK)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["labelled"] is True and body["reason"] is None
    assert body["label"] == GOED["label"]
    assert body["description"] == GOED["description"]
    assert body["model"] == "nep-model" and body["at"]
    assert len(model.prompts) == 1
    with session_factory() as s:
        assert s.get(Topic, tweede).llm_label is None


def test_a_rejected_answer_says_so(session_factory):
    index = InMemoryIndex()
    eerste, _ = _twee(session_factory, index)
    model = Model({"label": "zie https://example.org", "description": "Goed."})

    r = _app(session_factory, index, model).post(f"/topics/{eerste}/label",
                                                 headers=MARK)

    assert r.status_code == 200
    assert (r.json()["labelled"], r.json()["reason"]) == (False, "rejected")
    assert r.json()["label"] is None


def test_a_topic_without_summaries_says_so_and_calls_no_model(session_factory):
    index = InMemoryIndex()
    eerste, _ = _twee(session_factory, index, samenvatting=None)
    model = Model()

    r = _app(session_factory, index, model).post(f"/topics/{eerste}/label",
                                                 headers=MARK)

    assert (r.json()["labelled"], r.json()["reason"]) == (False, "no_summaries")
    assert model.prompts == []


def test_an_unknown_topic_is_404(session_factory):
    index = InMemoryIndex()
    _twee(session_factory, index)
    r = _app(session_factory, index, Model()).post(f"/topics/{uuid4()}/label",
                                                   headers=MARK)
    assert r.status_code == 404


def test_a_model_that_is_down_is_503_naming_the_model(session_factory):
    index = InMemoryIndex()
    eerste, _ = _twee(session_factory, index)
    r = _app(session_factory, index, Kapot()).post(f"/topics/{eerste}/label",
                                                   headers=MARK)
    assert r.status_code == 503
    assert "language model" in r.json()["detail"]
    with session_factory() as s:
        assert s.get(Topic, eerste).llm_label is None


def test_an_index_that_is_down_is_503_naming_the_index(session_factory):
    class Weg(InMemoryIndex):
        def documents_in(self, dossier, limit=10000):
            raise SearchUnavailable("index weg")

    eerste, _ = _twee(session_factory, InMemoryIndex())
    model = Model()
    r = _app(session_factory, Weg(), model).post(f"/topics/{eerste}/label",
                                                 headers=MARK)
    assert r.status_code == 503
    assert "search index" in r.json()["detail"]
    assert model.prompts == []


def test_without_a_model_the_route_says_so(session_factory):
    index = InMemoryIndex()
    eerste, _ = _twee(session_factory, index)
    r = _app(session_factory, index, None).post(f"/topics/{eerste}/label",
                                                headers=MARK)
    assert r.status_code == 503 and "language model" in r.json()["detail"]


def test_a_caller_who_may_not_read_the_corpus_is_refused_before_the_model(
        session_factory):
    index = InMemoryIndex()
    eerste, _ = _twee(session_factory, index)
    model = Model()

    r = _app(session_factory, index, model).post(f"/topics/{eerste}/label",
                                                 headers=GAST)

    assert r.status_code == 403
    assert model.prompts == []
    with session_factory() as s:
        assert s.get(Topic, eerste).llm_label is None


def test_no_route_labels_a_whole_dossier(session_factory):
    index = InMemoryIndex()
    _twee(session_factory, index)
    with session_factory() as s:
        from sqlalchemy import select

        from wordsworth.models import Dossier
        dossier_id = s.execute(select(Dossier.id)).scalar_one()
    model = Model()

    r = _app(session_factory, index, model).post(
        f"/dossiers/{dossier_id}/topics/labels", headers=MARK)

    assert r.status_code in (404, 405)
    assert model.prompts == []
