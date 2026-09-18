# SPDX-License-Identifier: MIT
"""Onderwerpen per dossier (onderwerpen): de berekening, de naam en de grens.

DB-gebonden, want de beschrijving van een onderwerp staat in Postgres en het
lidmaatschap in de index — deze tests toetsen juist dat die twee bij elkaar
blijven.
"""
from __future__ import annotations

import pytest

from wordsworth import topics as tp
from wordsworth.dossiers import ensure
from wordsworth.models import Topic
from wordsworth.search_index import InMemoryIndex


def _index_doc(index, doc_id, text, vector, dossiers):
    index.index(doc_id, text, f"documents/{doc_id}", vector=vector,
                dossiers=dossiers)


def _dossier(session, naam="zaak"):
    d = ensure(session, naam)
    session.flush()
    return d


def _twee_groepen(index, dossier_id, n=4):
    """Twee duidelijk gescheiden groepen: vergunningen en subsidies."""
    for i in range(n):
        _index_doc(index, f"v{i}", f"vergunning kapvergunning aanvraag boom {i}",
                   [1.0, 0.0, 0.0], [dossier_id])
    for i in range(n):
        _index_doc(index, f"s{i}", f"subsidie toekenning cultuur regeling {i}",
                   [0.0, 1.0, 0.0], [dossier_id])


def test_it_finds_the_groups_that_are_there(session_factory):
    with session_factory() as s:
        d = _dossier(s)
        index = InMemoryIndex()
        _twee_groepen(index, str(d.id))
        uitkomst = tp.compute(s, index, d.id, min_size=3)
        assert len(uitkomst.topics) == 2
        assert uitkomst.seen == 8 and uitkomst.with_vector == 8
        assert uitkomst.without_topic == 0
        assert {t.document_count for t in uitkomst.topics} == {4}


def test_the_name_comes_from_what_sets_the_group_apart(session_factory):
    with session_factory() as s:
        d = _dossier(s)
        index = InMemoryIndex()
        _twee_groepen(index, str(d.id))
        namen = " | ".join(t.computed_name for t in tp.compute(s, index, d.id).topics)
        assert "vergunning" in namen and "subsidie" in namen


def test_a_token_never_becomes_part_of_a_name(session_factory):
    """De spec-eis waar het om gaat. Een onderwerpnaam belandt op een scherm, in
    een export en in een URL — plekken waar de reveal-gate nooit kijkt.

    Hier is het token de sterkste term die er is: hij staat in elk document van
    de groep en in geen enkel document daarbuiten. Een naamgeving die tokens
    niet uitsluit, kiest hem dus gegarandeerd.
    """
    with session_factory() as s:
        d = _dossier(s)
        index = InMemoryIndex()
        for i in range(4):
            _index_doc(index, f"a{i}",
                       f"brief aan [PERSOON:3fa9c2d1] over vergunning {i}",
                       [1.0, 0.0, 0.0], [str(d.id)])
        for i in range(4):
            _index_doc(index, f"b{i}", f"subsidie cultuur regeling {i}",
                       [0.0, 1.0, 0.0], [str(d.id)])
        for topic in tp.compute(s, index, d.id).topics:
            assert "3fa9c2d1" not in topic.computed_name
            assert "persoon" not in topic.computed_name.lower()
            assert "[" not in topic.computed_name


def test_a_group_smaller_than_the_minimum_is_not_a_topic(session_factory):
    with session_factory() as s:
        d = _dossier(s)
        index = InMemoryIndex()
        for i in range(4):
            _index_doc(index, f"v{i}", f"vergunning boom {i}", [1.0, 0.0, 0.0],
                       [str(d.id)])
        _index_doc(index, "los", "iets heel anders over paspoorten",
                   [0.0, 0.0, 1.0], [str(d.id)])
        uitkomst = tp.compute(s, index, d.id, min_size=3)
        assert len(uitkomst.topics) == 1
        assert uitkomst.without_topic == 1
        assert index.documents_in(str(d.id))
        assert [d_ for d_ in index.documents_in(str(d.id))
                if d_.document_id == "los"][0].topics == []


def test_documents_without_a_vector_are_counted_not_hidden(session_factory):
    """Een document zonder vector kan niet meedoen. Dat mag, maar het hoort in
    het antwoord te staan — anders leest een lijst van 4 onderwerpen over 8
    documenten als een uitspraak over alle 12."""
    with session_factory() as s:
        d = _dossier(s)
        index = InMemoryIndex()
        _twee_groepen(index, str(d.id))
        _index_doc(index, "leeg", "geen vector", None, [str(d.id)])
        uitkomst = tp.compute(s, index, d.id)
        assert uitkomst.seen == 9 and uitkomst.with_vector == 8
        assert uitkomst.without_topic == 1


def test_recomputing_replaces_and_does_not_stack(session_factory):
    with session_factory() as s:
        d = _dossier(s)
        index = InMemoryIndex()
        _twee_groepen(index, str(d.id))
        eerst = tp.compute(s, index, d.id)
        s.flush()
        opnieuw = tp.compute(s, index, d.id)
        s.flush()
        assert len(tp.listing(s, d.id)) == len(opnieuw.topics) == 2
        oude = {str(t.id) for t in eerst.topics}
        for doc in index.documents_in(str(d.id)):
            assert not (set(doc.topics) & oude), "een oud onderwerp bleef plakken"


def test_another_dossiers_topic_survives_a_recompute(session_factory):
    """Een document kan in twee dossiers zitten en dus in twee onderwerpen. Het
    ene dossier herberekenen mag het andere niet wissen — dat is hoe een
    onderwerpenlijst stilletjes leegloopt."""
    with session_factory() as s:
        een = _dossier(s, "een")
        twee = _dossier(s, "twee")
        index = InMemoryIndex()
        for i in range(4):
            _index_doc(index, f"v{i}", f"vergunning kap boom {i}", [1.0, 0.0, 0.0],
                       [str(een.id), str(twee.id)])
        for i in range(4):
            _index_doc(index, f"s{i}", f"subsidie cultuur regeling {i}",
                       [0.0, 1.0, 0.0], [str(een.id), str(twee.id)])
        van_twee = tp.compute(s, index, twee.id)
        s.flush()
        tp.compute(s, index, een.id)
        s.flush()
        blijft = {str(t.id) for t in van_twee.topics}
        gevonden = set()
        for doc in index.documents_in(str(een.id)):
            gevonden |= set(doc.topics) & blijft
        assert gevonden == blijft, "het onderwerp van het andere dossier is weg"


def test_renaming_keeps_the_computed_name(session_factory):
    with session_factory() as s:
        d = _dossier(s)
        index = InMemoryIndex()
        _twee_groepen(index, str(d.id))
        topic = tp.compute(s, index, d.id).topics[0]
        berekend = topic.computed_name
        tp.rename(s, topic.id, "Kapvergunningen 2022")
        opnieuw = s.get(Topic, topic.id)
        assert opnieuw.given_name == "Kapvergunningen 2022"
        assert opnieuw.computed_name == berekend
        assert tp.display_name(opnieuw) == "Kapvergunningen 2022"
        tp.rename(s, topic.id, "  ")
        assert tp.display_name(s.get(Topic, topic.id)) == berekend


def test_renaming_something_that_is_not_there(session_factory):
    from uuid import uuid4
    with session_factory() as s:
        with pytest.raises(tp.TopicError):
            tp.rename(s, uuid4(), "x")


def test_the_mapping_is_ensured_before_a_topic_is_ever_written(session_factory):
    """`topics` is een nieuw veld en `ensure_ready` draait in productie alleen
    bij ingest. Schrijft de eerste `set_topics` het veld terwijl de mapping het
    niet kent, dan mapt OpenSearch het dynamisch: een lijst strings wordt `text`
    met een `.keyword`-subveld, en het `term`-filter matcht daarna niets —
    zonder fout, met "niets gevonden" als antwoord.

    Dat is letterlijk wat er op 2026-09-18 met `dossiers` gebeurde. De volgorde
    is de reparatie, dus die wordt hier getoetst.
    """
    class Volgorde(InMemoryIndex):
        def __init__(self):
            super().__init__()
            self.stappen = []

        def ensure_ready(self):
            self.stappen.append("ensure_ready")

        def set_topics(self, document_id, topics):
            self.stappen.append("set_topics")
            return super().set_topics(document_id, topics)

    with session_factory() as s:
        d = _dossier(s, "volgorde")
        index = Volgorde()
        _twee_groepen(index, str(d.id))
        tp.compute(s, index, d.id)
        assert "set_topics" in index.stappen, "er is niets geschreven"
        assert index.stappen[0] == "ensure_ready"
