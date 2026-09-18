# SPDX-License-Identifier: MIT
"""The generated evaluation corpus and its ground truth (ground-truth-corpus)."""
import importlib.util
import json
import random
from pathlib import Path

import pytest

from wordsworth.detectors import find_deterministic, is_valid_bsn, is_valid_iban
from wordsworth.eval.synthetic import Document, bsn, iban

_spec = importlib.util.spec_from_file_location(
    "generate_ground_truth",
    Path(__file__).resolve().parents[1] / "scripts/eval/generate_ground_truth.py")
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)


def test_identifiers_are_valid_but_generated():
    """An invalid BSN tests nothing — the detector rejects it and the corpus
    proves only that rejection works."""
    rng = random.Random(7)
    assert all(is_valid_bsn(bsn(rng)) for _ in range(300))
    assert all(is_valid_iban(iban(rng)) for _ in range(300))


def test_a_span_is_exactly_the_text_at_that_offset():
    d = Document("d", "t").lit("Betreft ").pii("Janine van Dijk", "PERSON").lit(".")
    e, = d.check().entities
    assert d.text[e["start"]:e["end"]] == "Janine van Dijk"


def test_a_corrupted_span_fails_the_corpus_rather_than_shipping():
    d = Document("d", "t").lit("x").pii("Janine", "PERSON")
    d.entities[0]["end"] += 99
    with pytest.raises(ValueError):
        d.check()


def test_overlapping_spans_are_refused():
    d = Document("d", "t").pii("Janine", "PERSON")
    d.entities.append({"start": 3, "end": 9, "type": "BSN"})
    with pytest.raises(ValueError):
        d.check()


def test_unlabelled_values_are_carried_but_not_gold():
    """GENDER has no detector. Scoring the detector on it would measure us."""
    d = Document("d", "t").unlabelled("vrouw", "GENDER").check()
    assert d.entities == [] and d.types == {"GENDER"}


def test_generated_corpus_is_internally_consistent(tmp_path):
    gen.main([str(tmp_path), "--count", "60", "--seed", "1"])
    lines = (tmp_path / "gold.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 60
    for raw in lines:
        doc = json.loads(raw)
        text = doc["text"]
        for e in doc["entities"]:
            assert 0 <= e["start"] < e["end"] <= len(text)
        assert text == (tmp_path / "documents" / f"{doc['id']}.txt").read_text(
            encoding="utf-8")


def test_every_document_is_judged_for_every_query(tmp_path):
    """A document missing from qrels is indistinguishable from one judged
    irrelevant, and the metrics differ."""
    from wordsworth.eval.collection import load_qrels, load_queries

    gen.main([str(tmp_path), "--count", "40", "--seed", "2"])
    queries = load_queries(tmp_path / "queries.tsv")
    qrels = load_qrels(tmp_path / "qrels.txt")
    assert set(qrels) == set(queries)
    assert all(len(judged) == 40 for judged in qrels.values())
    # relevance follows from the topic, so each query has relevant documents
    assert all(any(v for v in judged.values()) for judged in qrels.values())


def test_a_postcode_behind_postbus_is_seeded_and_not_gold(tmp_path):
    """The exception from measurement 01, checked at corpus scale: an
    organisation's Postbus address is in the text and out of the answers."""
    gen.main([str(tmp_path), "--count", "200", "--seed", "3"])
    seeded = found_in_gold = 0
    for raw in (tmp_path / "gold.jsonl").read_text(encoding="utf-8").splitlines():
        doc = json.loads(raw)
        for line in doc["text"].splitlines():
            if not line.startswith("Postbus "):
                continue
            seeded += 1
            at = doc["text"].index(line)
            found_in_gold += sum(
                1 for e in doc["entities"] if at <= e["start"] < at + len(line))
    assert seeded > 0 and found_in_gold == 0


def test_the_deterministic_layer_scores_perfectly_on_what_it_claims(tmp_path):
    """The corpus must not be harder than the detectors' own contract: every
    BSN/IBAN/EMAIL/POSTCODE in the gold is found, and nothing else is."""
    gen.main([str(tmp_path), "--count", "120", "--seed", "4"])
    deterministic = {"BSN", "IBAN", "EMAIL", "POSTCODE"}
    for raw in (tmp_path / "gold.jsonl").read_text(encoding="utf-8").splitlines():
        doc = json.loads(raw)
        found = {(s, e, lbl.upper()) for lbl, _, s, e in find_deterministic(doc["text"])}
        wanted = {(e["start"], e["end"], e["type"]) for e in doc["entities"]
                  if e["type"] in deterministic}
        assert found == wanted, doc["id"]


def test_the_manifest_counts_what_was_seeded(tmp_path):
    gen.main([str(tmp_path), "--count", "100", "--seed", "5"])
    m = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    gold = [json.loads(r) for r in
            (tmp_path / "gold.jsonl").read_text(encoding="utf-8").splitlines()]
    assert m["documents"] == 100
    assert m["entities"] == sum(len(d["entities"]) for d in gold)
    assert m["documents_carrying_gender_date_postcode"] > 0
    assert "lower bound" in m["caveat"]


def test_generation_is_deterministic(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    gen.main([str(a), "--count", "30", "--seed", "9"])
    gen.main([str(b), "--count", "30", "--seed", "9"])
    assert (a / "gold.jsonl").read_bytes() == (b / "gold.jsonl").read_bytes()
