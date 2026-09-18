# SPDX-License-Identifier: MIT
"""De onderwerpmeting (onderwerpen): indeling én zoeken, over één corpus."""
from __future__ import annotations

import json

from wordsworth import topics as tp
from wordsworth.dossiers import ensure
from wordsworth.eval.topics_run import (best_topic_per_query, computed_topics,
                                        known_topics, measure)
from wordsworth.search_index import InMemoryIndex

ONDERWERPEN = {
    "parkeren": ("parkeervergunning bewoners", "parkeervergunning bewoners zone",
                 [1.0, 0.0, 0.0]),
    "afval": ("afvalstoffenheffing diftar", "afvalstoffenheffing diftar container",
              [0.0, 1.0, 0.0]),
    "subsidie": ("subsidie sportvereniging", "subsidie sportvereniging jeugd",
                 [0.0, 0.0, 1.0]),
}


def _corpus(tmp_path, index, dossier_key, per=4):
    regels, queries, qrels = [], [], []
    for naam, (query, woorden, vec) in ONDERWERPEN.items():
        queries.append(f"q-{naam}\t{query}")
        for i in range(per):
            doc_id = f"{naam}-{i}"
            tekst = f"{woorden} nummer {i}"
            index.index(doc_id, tekst, doc_id, vector=vec, dossiers=[dossier_key])
            regels.append(json.dumps({"id": doc_id, "text": tekst,
                                      "entities": [], "topic": naam}))
    for naam in ONDERWERPEN:
        for ander in ONDERWERPEN:
            for i in range(per):
                qrels.append(f"q-{naam} 0 {ander}-{i} {1 if naam == ander else 0}")
    (tmp_path / "gold.jsonl").write_text("\n".join(regels), encoding="utf-8")
    (tmp_path / "queries.tsv").write_text("\n".join(queries), encoding="utf-8")
    (tmp_path / "qrels.txt").write_text("\n".join(qrels), encoding="utf-8")


def test_the_generator_writes_a_known_topic_per_document(tmp_path):
    """De spec-eis. Zonder dit is er geen waarheid om een indeling naast te
    leggen, en is 'de clustering ziet er goed uit' een gevoel."""
    from wordsworth.eval.synthetic import Document

    d = Document("doc-0001", "parkeren").lit("tekst").check()
    assert d.gold()["topic"] == "parkeren"


def test_it_reports_both_numbers(session_factory, tmp_path):
    index = InMemoryIndex()
    with session_factory() as s:
        dossier = ensure(s, "meting")
        s.flush()
        key = str(dossier.id)
        _corpus(tmp_path, index, key)
        tp.compute(s, index, dossier.id, min_size=3)
        s.commit()

    report = measure(index, key, tmp_path / "gold.jsonl",
                     tmp_path / "queries.tsv", tmp_path / "qrels.txt")

    # 1. De indeling klopt: drie duidelijk gescheiden groepen.
    assert report["grouping"]["adjusted_rand_index"] == 1.0
    assert report["grouping"]["purity"] == 1.0
    assert report["grouping"]["with_a_topic"] == 12
    assert report["grouping"]["documents_in_dossier"] == 12

    # 2. Het zoeken: beide kanten gemeten, niet één.
    assert set(report["retrieval"]) == {"unscoped", "topic_scoped"}
    for kant in report["retrieval"].values():
        assert set(kant) == {"r_precision", "recall@10", "map", "ndcg@10"}


def test_the_scoped_run_does_not_lose_relevant_documents(session_factory, tmp_path):
    """De verwachting stond vooraf opgeschreven: het zoeken beweegt niet of
    nauwelijks. Wat NIET mag is dat het omlaag gaat — dan gooit de scope juiste
    documenten weg, en dat is precies het risico van filteren."""
    index = InMemoryIndex()
    with session_factory() as s:
        dossier = ensure(s, "meting2")
        s.flush()
        key = str(dossier.id)
        _corpus(tmp_path, index, key)
        tp.compute(s, index, dossier.id, min_size=3)
        s.commit()
    report = measure(index, key, tmp_path / "gold.jsonl",
                     tmp_path / "queries.tsv", tmp_path / "qrels.txt")
    zonder = report["retrieval"]["unscoped"]
    met = report["retrieval"]["topic_scoped"]
    for metriek in zonder:
        assert met[metriek] >= zonder[metriek] - 1e-9, (
            f"{metriek} ging omlaag door de scope: {zonder[metriek]} -> {met[metriek]}")


def test_documents_without_a_topic_are_a_separate_number(session_factory, tmp_path):
    index = InMemoryIndex()
    with session_factory() as s:
        dossier = ensure(s, "meting3")
        s.flush()
        key = str(dossier.id)
        _corpus(tmp_path, index, key)
        # Tegengesteld aan alles: cosinusafstand 1 of meer tot elke groep, dus
        # geen enkel cluster neemt hem op.
        index.index("los-0", "iets heel anders", "los-0", vector=[-1.0, 0.0, 0.0],
                    dossiers=[key])
        tp.compute(s, index, dossier.id, min_size=3)
        s.commit()
    report = measure(index, key, tmp_path / "gold.jsonl",
                     tmp_path / "queries.tsv", tmp_path / "qrels.txt")
    g = report["grouping"]
    assert g["documents_in_dossier"] == 13
    assert g["with_a_topic"] == 12
    # Het losse document staat niet in de waarheid en telt dus niet mee in de
    # ARI -- die blijft 1.0, en het verschil staat in de twee tellingen.
    assert g["adjusted_rand_index"] == 1.0


def test_a_query_without_a_topic_is_not_a_hole(session_factory, tmp_path):
    index = InMemoryIndex()
    with session_factory() as s:
        dossier = ensure(s, "meting4")
        s.flush()
        key = str(dossier.id)
        _corpus(tmp_path, index, key)
        tp.compute(s, index, dossier.id, min_size=3)
        s.commit()
    truth = known_topics(tmp_path / "gold.jsonl")
    found = computed_topics(index, key)
    gekozen = best_topic_per_query(truth, found, {"q-onbekend": "iets anders"})
    assert gekozen == {}, "een query zonder onderwerp hoort er niet in te staan"
