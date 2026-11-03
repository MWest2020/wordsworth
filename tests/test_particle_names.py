"""particle-names-rule: the gazetteer loader, the pattern, and the wiring into
`ReversibleAnonymizer`. Step 1 of 4, split from `detect-dutch-particle-names`
(#285)."""
from __future__ import annotations

import json

import pytest

from wordsworth import particle_names
from wordsworth.eval.synthetic import VOORNAMEN
from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import InMemoryMappingStore
from wordsworth.openanonymiser_driver import OpenAnonymiserAnonymizer
from wordsworth.pseudonymizer import ReversibleAnonymizer


# --- 1. Rule and gazetteer ------------------------------------------------


def test_shipped_gazetteer_loads_through_importlib_resources():
    names = particle_names.load_gazetteer()
    assert names  # non-empty
    assert all(isinstance(n, str) and n for n in names)


def test_every_shipped_entry_has_a_non_empty_reden():
    import importlib.resources

    raw = importlib.resources.files("wordsworth").joinpath(
        "data/voornamen.json").read_text(encoding="utf-8")
    for entry in json.loads(raw):
        assert str(entry.get("reden", "")).strip(), entry


def test_a_missing_gazetteer_file_is_a_hard_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        particle_names.load_gazetteer(tmp_path / "does-not-exist.json")


def test_an_entry_without_a_reden_is_refused_and_named(tmp_path):
    path = tmp_path / "voornamen.json"
    path.write_text(json.dumps([{"naam": "Pietje", "reden": ""}]))
    with pytest.raises(ValueError, match="Pietje"):
        particle_names.load_gazetteer(path)
    path.write_text(json.dumps([{"naam": "Pietje"}]))
    with pytest.raises(ValueError, match="Pietje"):
        particle_names.load_gazetteer(path)


@pytest.mark.parametrize("particle", particle_names.PARTICLES)
def test_each_particle_is_one_person_span(particle):
    text = f"Pieter {particle} Berg was aanwezig."
    full_name = f"Pieter {particle} Berg"
    ents = particle_names.detect(text)
    assert len(ents) == 1
    e = ents[0]
    assert e.entity_type == "PERSON"
    assert e.text == full_name
    assert e.layer == "dutch_particle_name"
    assert text[e.start:e.end] == full_name


def test_ordinary_text_with_a_lowercase_particle_yields_no_person():
    text = "Dit besluit gaat over de van ouds bekende regeling."
    assert particle_names.detect(text) == []


@pytest.mark.parametrize("zin", [
    "De zaak werd voorgelegd aan de Raad van State.",
    "De Kamer van Koophandel registreerde de wijziging.",
    "Het Ministerie van Binnenlandse Zaken reageerde niet.",
    "De Vereniging van Eigenaren vergaderde donderdag.",
    "Het Hoogheemraadschap van Rijnland gaf een vergunning af.",
])
def test_institutions_are_not_names(zin):
    assert particle_names.detect(zin) == []


def test_anchor_is_the_gazetteer():
    assert particle_names.detect("Bakker van Dijk kwam langs.") == []
    assert particle_names.detect("Pieter van Dijk kwam langs.") != []


def test_ton_wil_bart_are_not_entries():
    names = particle_names.load_gazetteer()
    assert "Ton" not in names
    assert "Wil" not in names
    assert "Bart" not in names


@pytest.mark.parametrize("zin", [
    "Ton van der Berg kwam langs.",
    "Bart de Groot kwam langs.",
])
def test_ton_and_bart_yield_no_person_from_this_rule(zin):
    assert particle_names.detect(zin) == []


def test_exactly_ton_and_bart_stay_unmatched_over_the_synthetic_voornamen():
    # Ton and Bart are common capitalised words (precision over recall,
    # design.md) -- an accepted miss, checked here by name so a future
    # gazetteer edit cannot silently change which names this costs.
    unmatched = []
    for naam in VOORNAMEN:
        zin = f"{naam} van der Berg kwam langs."
        if not particle_names.detect(zin):
            unmatched.append(naam)
    assert sorted(unmatched) == ["Bart", "Ton"]


def test_gazetteer_content_does_not_change_lists_hash(tmp_path):
    from wordsworth.detection_lists import DetectionLists

    (tmp_path / "allow.json").write_text("{}")
    (tmp_path / "deny.json").write_text("{}")
    before = DetectionLists.load(tmp_path).hash

    gazetteer = tmp_path / "voornamen.json"
    gazetteer.write_text(json.dumps([{"naam": "Pietje", "reden": "test"}]))
    assert particle_names.load_gazetteer(gazetteer) == ["Pietje"]
    gazetteer.write_text(json.dumps([{"naam": "Klaasje", "reden": "test"}]))
    assert particle_names.load_gazetteer(gazetteer) == ["Klaasje"]

    after = DetectionLists.load(tmp_path).hash
    assert before == after


# --- 2. Wiring -------------------------------------------------------------


def test_reversible_anonymizer_adds_particle_name_detections_before_lists():
    text = ("Pieter ter Berg was aanwezig. Verder gaat het over de van ouds "
            "bekende regeling.")
    r = ReversibleAnonymizer(InMemoryKeyProvider(), InMemoryMappingStore(),
                              detect=lambda t: []).anonymize(text)
    assert "Pieter ter Berg" not in r.text
    assert "de van ouds" in r.text  # unrelated lowercase 'van' may remain
    agg = r.detections["dutch_particle_name"]["PERSON"]
    assert agg["count"] == 1
    assert set(agg) == {"count", "min_score", "max_score", "below_threshold"}


def test_irreversible_driver_is_out_of_scope():
    text = "Pieter ter Berg was aanwezig."
    r = OpenAnonymiserAnonymizer(engine=lambda t: (t, {})).anonymize(text)
    assert "dutch_particle_name" not in r.detections
    assert "Pieter ter Berg" in r.text


# --- 3. Outside the deterministic table ------------------------------------


def test_not_a_deterministic_detector():
    from wordsworth import detectors
    from wordsworth.eval.pii import deterministic_entities

    assert sorted(label for label, *_ in detectors.DETECTORS) == [
        "bsn", "email", "iban", "postcode"]
    assert detectors.find_deterministic("Pieter van der Berg") == []
    assert deterministic_entities("Pieter van der Berg") == []
