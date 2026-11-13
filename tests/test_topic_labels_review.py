# SPDX-License-Identifier: MIT
"""De bevindingen uit de review van #433 (topic-labels-llm): herkomst overal
waar het label staat, de logregel in productie, een herberekening tijdens het
labelen, en het ene slot dat niet mag blijven hangen."""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from topic_label_setup import Model, dossier
from wordsworth import concurrency
from wordsworth.api import create_app
from wordsworth.models import Topic
from wordsworth.search_index import InMemoryIndex
from wordsworth.topic_labels import LABEL_SLOT, label_topics

KEY, NAAM = "s3cret", "zaak-review"


def _opzet(session_factory, generator):
    index = InMemoryIndex()
    with session_factory() as s:
        d, topics, _ = dossier(s, index, naam=NAAM, topics=[
            ("kap · boom", [([1.0, 0.0], "Een kapvergunning.")] * 2),
            ("geluid · evenement", [([0.0, 1.0], "Een evenement.")] * 2)])
        ids = [t.id for t in topics]
    app = create_app(session_factory=session_factory, api_keys={KEY: "mark"},
                     search_index=index, generator=generator)
    c = TestClient(app, base_url="https://testserver")
    c.post("/console/login", data={"key": KEY})
    return c, d.id, ids, index


@dataclass
class Verwijdert(Model):
    """Een model dat, terwijl het schrijft, het onderwerp laat verdwijnen:
    een herberekening van het dossier midden in de aanroep."""

    session_factory: object = None
    weg: object = None

    def label(self, prompt):
        if self.weg is not None and len(self.prompts) == 0:
            with self.session_factory() as s:
                s.execute(delete(Topic).where(Topic.id == self.weg))
                s.commit()
        return super().label(prompt)


def test_every_place_that_shows_the_label_says_it_is_a_models(session_factory):
    c, dossier_id, (eerste, _), _ = _opzet(session_factory, Model())
    c.post(f"/topics/{eerste}/label", headers={"x-api-key": KEY})
    with session_factory() as s:
        datum = s.get(Topic, eerste).llm_at.strftime("%Y-%m-%d")
    herkomst = f"geschreven door nep-model op {datum}"

    pagina = c.get(f"/console/dossier?dossier={NAAM}").text
    assert "Kap van bomen in het centrum" in pagina
    assert f"(taalmodel, {herkomst})" in pagina
    assert pagina.count("(taalmodel") == 1, "het onderwerp zonder label is geen claim"

    zoek = c.get("/console/search", params={"q": "document", "dossier": NAAM,
                                            "topic": str(eerste)}).text
    assert f"(taalmodel, {herkomst})" in zoek

    api = c.get(f"/dossiers/{dossier_id}/topics", headers={"x-api-key": KEY}).json()
    gelabeld = next(t for t in api["topics"] if t["id"] == str(eerste))
    assert gelabeld["name"] == gelabeld["llm_label"] == "Kap van bomen in het centrum"
    assert gelabeld["llm_model"] == "nep-model" and gelabeld["llm_at"]


def test_the_outcome_line_is_printed_under_the_production_logging(session_factory):
    """`serve.build_app` zet de logging aan zoals productie hem heeft; de
    uitkomst van een klik moet daar dan ook echt uit komen."""
    from wordsworth.serve import build_app

    build_app()
    pipeline = logging.getLogger("wordsworth.pipeline")
    (handler,) = [h for h in pipeline.handlers if isinstance(h, logging.StreamHandler)]
    uit = io.StringIO()
    oud = handler.setStream(uit)
    try:
        c, _, (eerste, _), _ = _opzet(session_factory, Model())
        c.post(f"/console/topics/{eerste}/label", data={"dossier": NAAM})
    finally:
        handler.setStream(oud)
    assert f'"topic_id": "{eerste}"' in uit.getvalue()
    assert '"outcome": "labelled"' in uit.getvalue()
    assert "Kap van bomen" not in uit.getvalue()


def test_a_topic_recomputed_during_the_call_counts_as_failed_and_the_run_goes_on(
        session, session_factory):
    index = InMemoryIndex()
    d, (eerste, tweede), _ = dossier(session, index, topics=[
        ("kap · boom", [([1.0, 0.0], "Een kapvergunning.")] * 2),
        ("geluid · evenement", [([0.0, 1.0], "Een evenement.")] * 2)])
    model = Verwijdert(session_factory=session_factory, weg=eerste.id)

    uit = label_topics(session, index, d.id, model)

    assert (uit.seen, uit.failed, uit.labelled) == (2, 1, 1)
    session.expire_all()
    assert session.get(Topic, tweede.id).llm_label is not None


def test_the_route_answers_409_when_the_topic_was_recomputed(session_factory):
    model = Verwijdert(session_factory=session_factory)
    c, _, (eerste, _), _ = _opzet(session_factory, model)
    model.weg = eerste

    r = c.post(f"/topics/{eerste}/label", headers={"x-api-key": KEY})

    assert r.status_code == 409
    assert r.json()["detail"] == "onderwerp is opnieuw berekend"


def test_the_route_shares_the_one_slot_and_answers_409(session_factory):
    model = Model()
    c, _, (eerste, _), _ = _opzet(session_factory, model)
    slot = concurrency.limiter(LABEL_SLOT, 1)
    assert slot.acquire(blocking=False)
    try:
        r = c.post(f"/topics/{eerste}/label", headers={"x-api-key": KEY})
    finally:
        slot.release()
    assert r.status_code == 409
    assert r.json()["detail"] == "er loopt al een label-opdracht"
    assert model.prompts == []
    assert c.post(f"/topics/{eerste}/label",
                  headers={"x-api-key": KEY}).status_code == 200


def test_a_page_that_fails_to_render_does_not_keep_the_slot(session_factory,
                                                           monkeypatch):
    from wordsworth import console_topics

    model = Model()
    c, _, (eerste, _), _ = _opzet(session_factory, model)

    def kapot(session, dossier_id):
        raise RuntimeError("de pagina valt om")

    monkeypatch.setattr(console_topics, "_rows", kapot)
    with pytest.raises(RuntimeError):
        c.post(f"/console/topics/{eerste}/label", data={"dossier": NAAM})

    slot = concurrency.limiter(LABEL_SLOT, 1)
    assert slot.acquire(blocking=False), "het slot bleef vast na een fout"
    slot.release()
    assert model.prompts == [], "zonder pagina ook geen label"
