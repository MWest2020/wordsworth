"""add-pii-detection-eval: span/token P-R-F1 per type, leaks, per-layer."""
from pathlib import Path

import pytest

from wordsworth.eval.pii import (
    GoldDoc, GoldSpan, deterministic_entities, evaluate_pii, load_gold, score_doc,
)
from wordsworth.eval.pii_run import build_detect, format_report, main
from wordsworth.openanonymiser_driver import Entity

FIX = Path(__file__).parent / "fixtures" / "pii_gold_synthetic.jsonl"


def _doc():
    text = "Aanvrager Janine van Dijk, BSN 123456782."
    return GoldDoc("d", text, [GoldSpan(10, 25, "PERSON"), GoldSpan(31, 40, "BSN")])


def test_partial_match_span_vs_token():
    doc = _doc()
    preds = [Entity("PERSON", "van Dijk", 17, 25, "openanonymiser", 0.9)]
    r = score_doc(doc, preds)
    assert r["span"]["PERSON"].tp == 0 and r["span"]["PERSON"].fn == 1
    tok = r["token"]["PERSON"]
    assert (tok.tp, tok.fn, tok.fp) == (2, 1, 0)       # token recall 2/3
    assert r["leaks"] == 1                              # the BSN: no overlap at all


def test_missed_entity_is_a_leak_and_exact_match_counts():
    doc = _doc()
    preds = [Entity("PERSON", "Janine van Dijk", 10, 25, "openanonymiser", 0.9),
             Entity("BSN", "123456782", 31, 40, "deterministic", 1.0)]
    r = score_doc(doc, preds)
    assert r["leaks"] == 0
    assert r["span"]["PERSON"].prf()["f1"] == 1.0 and r["span"]["BSN"].prf()["recall"] == 1.0
    r2 = score_doc(doc, preds[:1])
    assert r2["leaks"] == 1 and r2["span"]["BSN"].fn == 1


def test_false_positive_counts_against_precision():
    doc = _doc()
    preds = [Entity("PERSON", "Aanvrager", 0, 9, "openanonymiser", 0.5)]
    r = score_doc(doc, preds)
    assert r["span"]["PERSON"].fp == 1 and r["token"]["PERSON"].fp == 1
    assert r["span"]["PERSON"].prf()["precision"] == 0.0


def test_load_gold_validates_spans(tmp_path):
    bad = tmp_path / "g.jsonl"
    bad.write_text('{"id":"x","text":"abc","entities":[{"start":2,"end":9,"type":"PERSON"}]}\n')
    with pytest.raises(ValueError):
        load_gold(bad)
    bad.write_text('{"id":"x","text":"abcdef","entities":[{"start":0,"end":3,"type":"A"},'
                   '{"start":2,"end":4,"type":"B"}]}\n')
    with pytest.raises(ValueError):
        load_gold(bad)
    docs = load_gold(FIX)
    assert len(docs) == 10 and sum(len(d.entities) for d in docs) == 20


def test_deterministic_layer_on_fixture_and_per_layer_report():
    docs = load_gold(FIX)
    report = evaluate_pii(docs, deterministic_entities)
    det = report["per_layer"]["deterministic"]["overall"]["span"]
    assert det["precision"] == 1.0                        # validated detectors: no FP
    assert report["span"]["BSN"]["recall"] == 1.0 and report["span"]["IBAN"]["recall"] == 1.0
    assert report["span"]["EMAIL"]["recall"] == 1.0
    # names/places are not the deterministic layer's job: they show up as leaks
    assert report["leaks"] == sum(1 for d in docs for e in d.entities
                                  if e.type in ("PERSON", "LOCATION", "PHONE_NUMBER"))
    assert report["documents"] == 10 and report["gold_entities"] == 20


def test_cli_runs_deterministic_layer(capsys):
    assert main([str(FIX), "--layers", "deterministic"]) == 0
    out = capsys.readouterr().out
    assert "leaks=" in out and "BSN" in out and "layer deterministic" in out
    assert main([str(FIX), "--layers", "deterministic", "--json"]) == 0
    assert '"per_layer"' in capsys.readouterr().out
    with pytest.raises(ValueError):
        build_detect(["nope"])
    assert "overall/span" in format_report(evaluate_pii(load_gold(FIX), deterministic_entities))
