# SPDX-License-Identifier: MIT
"""De kern van topic-labels-llm: welke samenvattingen het model ziet, wat er
wordt afgewezen, en wat er gebeurt als het model of de index weg is.

Geen Ollama: een nep-generator (`topic_label_setup.Model`). Deze tests
bewijzen het loodgieterswerk en de controle, niet de kwaliteit van een label.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from topic_label_setup import GOED, Kapot, Model, dossier
from wordsworth.db import init_schema, make_engine
from wordsworth.models import Topic
from wordsworth.search_index import InMemoryIndex, SearchUnavailable
from wordsworth.topic_labels import (NO_SUMMARIES, REJECTED, label_topic,
                                     label_topics)
from wordsworth.topics import display_name


def test_a_valid_answer_is_stored_from_the_eight_most_central_summaries(session):
    """Tien leden: acht dicht bij elkaar, twee ver weg. Het zwaartepunt ligt
    bij de acht, dus hun samenvattingen gaan naar het model en die van de twee
    uitschieters niet."""
    leden = [([1.0, 0.01 * i], f"centraal-{i}") for i in range(8)]
    leden += [([0.0, 1.0], "uitschieter-a"), ([0.0, 1.1], "uitschieter-b")]
    index = InMemoryIndex()
    _, (topic,), _ = dossier(session, index,
                             topics=[("kap · boom · vergunning", leden)])
    model = Model()

    assert label_topic(session, index, topic.id, model) == "labelled"

    (prompt,) = model.prompts
    for i in range(8):
        assert f"centraal-{i}" in prompt
    assert "uitschieter" not in prompt
    assert "TERMEN: kap, boom, vergunning" in prompt
    session.expire_all()
    opgeslagen = session.get(Topic, topic.id)
    assert opgeslagen.llm_label == GOED["label"]
    assert opgeslagen.llm_description == GOED["description"]
    assert opgeslagen.llm_model == "nep-model"
    assert opgeslagen.llm_at is not None


_ZEVEN = "een twee drie vier vijf zes zeven"


@pytest.mark.parametrize("antwoord", [
    {"label": _ZEVEN, "description": "Goed."},
    {"label": "", "description": "Goed."},
    {"label": "   ", "description": "Goed."},
    {"label": "[PERSON:3fa9c2d1] kapt bomen", "description": "Goed."},
    {"label": "PERSON:3fa9c2d1 kapt bomen", "description": "Goed."},
    {"label": "bomen bij 9e9d0346", "description": "Goed."},
    {"label": "[PERSOON] kapt bomen", "description": "Goed."},
    {"label": "zie https://example.org/a", "description": "Goed."},
    {"label": "zie www.example.org", "description": "Goed."},
    {"label": "Bomen", "description": "Eerste regel.\nTweede regel."},
    {"label": "Bomen", "description": "x" * 201},
    {"label": "Bomen", "description": ""},
    {"label": "Bomen", "description": "Over [LOCATION:9e9d0346] en de kap."},
    {"label": "Bomen", "description": "Over LOCATION:9e9d0346 en de kap."},
    {"label": "Bomen", "description": "Brief van [NAAM] over de kap."},
    {"label": "Bomen", "description": "Zie http://gemeente.example.nl."},
    {"label": "Bomen"},
    {"label": 7, "description": "Goed."},
], ids=["zeven-woorden", "leeg", "spaties", "token", "token-zonder-haken",
        "kale-id", "plaatshouder", "url", "www", "twee-regels", "te-lang",
        "lege-beschrijving", "token-in-beschrijving",
        "token-zonder-haken-in-beschrijving", "plaatshouder-in-beschrijving",
        "url-in-beschrijving", "geen-beschrijving", "geen-tekst"])
def test_an_invalid_answer_is_rejected_and_the_topic_keeps_what_it_had(
        session, antwoord):
    index = InMemoryIndex()
    _, (topic,), _ = dossier(session, index)
    topic.llm_label, topic.llm_description = "Oud label", "Oude zin."
    session.commit()

    assert label_topic(session, index, topic.id, Model(antwoord)) == REJECTED

    session.expire_all()
    na = session.get(Topic, topic.id)
    assert (na.llm_label, na.llm_description) == ("Oud label", "Oude zin.")
    assert na.llm_model is None


def test_six_words_and_two_hundred_characters_are_still_allowed(session):
    index = InMemoryIndex()
    _, (topic,), _ = dossier(session, index)
    model = Model({"label": "een twee drie vier vijf zes", "description": "x" * 200})
    assert label_topic(session, index, topic.id, model) == "labelled"


def test_a_topic_without_summaries_is_not_sent_to_the_model(session):
    index = InMemoryIndex()
    _, (topic,), _ = dossier(session, index, topics=[
        ("kap · boom", [([1.0, 0.0], None)] * 3)])
    model = Model()

    uit = label_topics(session, index, topic.dossier_id, model)

    assert model.prompts == []
    assert (uit.seen, uit.no_summaries, uit.labelled) == (1, 1, 0)
    assert label_topic(session, index, topic.id, model) == NO_SUMMARIES
    assert model.prompts == []


def _drie(session, index):
    return dossier(session, index, topics=[
        (f"term{n} · ander{n}", [([float(n), 1.0], f"samenvatting {n}")] * 2)
        for n in range(3)])


def test_a_model_that_is_down_leaves_every_topic_with_its_name(session):
    index = InMemoryIndex()
    d, topics, _ = _drie(session, index)

    uit = label_topics(session, index, d.id, Kapot())

    assert (uit.seen, uit.failed, uit.labelled) == (3, 3, 0)
    session.expire_all()
    for t in topics:
        assert session.get(Topic, t.id).llm_label is None
        assert display_name(session.get(Topic, t.id)) == t.computed_name


def test_one_failed_call_costs_that_topic_only(session):
    index = InMemoryIndex()
    d, _, _ = _drie(session, index)

    uit = label_topics(session, index, d.id, Kapot(bij=2))

    assert (uit.seen, uit.labelled, uit.failed) == (3, 2, 1)


class _Weg(InMemoryIndex):
    def documents_in(self, dossier, limit=10000):
        raise SearchUnavailable("index weg")


def test_an_unreachable_index_labels_nothing_and_says_so(session):
    index = InMemoryIndex()
    d, (topic,), _ = dossier(session, index)
    model = Model()

    with pytest.raises(SearchUnavailable):
        label_topics(session, _Weg(), d.id, model)
    with pytest.raises(SearchUnavailable):
        label_topic(session, _Weg(), topic.id, model)

    assert model.prompts == []
    session.expire_all()
    assert session.get(Topic, topic.id).llm_label is None


def test_the_four_columns_are_added_to_an_existing_database(session_factory,
                                                            database_url):
    engine = make_engine(database_url)
    kolommen = ("llm_label", "llm_description", "llm_model", "llm_at")
    with engine.begin() as conn:
        for k in kolommen:
            conn.execute(text(f"ALTER TABLE topics DROP COLUMN {k}"))

    init_schema(engine)

    with engine.connect() as conn:
        gevonden = {r[0] for r in conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'topics'"))}
    assert set(kolommen) <= gevonden


def test_display_name_prefers_a_person_then_the_model_then_the_terms():
    t = Topic(computed_name="kap · boom · vergunning")
    assert display_name(t) == "kap · boom · vergunning"
    t.llm_label = "Kap van bomen"
    assert display_name(t) == "Kap van bomen"
    t.given_name = "Bomenkap centrum"
    assert display_name(t) == "Bomenkap centrum"
    assert t.computed_name == "kap · boom · vergunning", "de termen blijven"
