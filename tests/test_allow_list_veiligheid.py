# SPDX-License-Identifier: MIT
"""De rem op de allow-lijst (overdetectie).

Een allow-regel haalt bescherming wég — de enige plek in dit systeem waar een
wijziging stilletjes tot mínder pseudonimisering leidt. Deze toets is de reden
dat zo'n lijst er überhaupt mag zijn: het evalcorpus weet wat er aan PII in zit,
dus "deze regel verbergt een echte waarde" is een feit dat vóór het uitrollen
vaststaat in plaats van een kwestie van vertrouwen.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from wordsworth.detection_lists import DetectionLists

LIJSTEN = Path(__file__).resolve().parent.parent / "lists"


def _ingezaaide_waarden() -> list[tuple[str, str]]:
    """(type, waarde) van alles wat de generator als PII in het corpus zet,
    **plus de losse woorden daarvan**.

    Die tweede helft is waar het op aankomt. Het corpus zaait volledige namen
    ("Hendrik de Vries"), maar de detector levert in de praktijk ook losse
    achternamen. Toetste deze rem alleen op de volledige waarde, dan glipte een
    regel als `^vries$` erdoor — precies het gevaarlijke geval. Gemeten:
    mijn eerste versie deed dat.
    """
    import sys

    sys.path.insert(0, str(LIJSTEN.parent))
    from scripts.eval.generate_ground_truth import TOPICS, build

    rng = random.Random(20260917)
    onderwerpen = list(TOPICS)
    uit = []
    for i in range(120):
        doc = build(f"doc-{i:04d}", onderwerpen[i % len(onderwerpen)], rng)
        for e in doc.entities:
            waarde = doc.text[e["start"]:e["end"]]
            uit.append((e["type"], waarde))
            for woord in waarde.split():
                if len(woord) >= 3:
                    uit.append((e["type"], woord))
    return uit


def test_the_lists_load_at_all():
    lijsten = DetectionLists.load(LIJSTEN)
    assert lijsten.allow, "geen allow-regels geladen"
    assert lijsten.hash, "zonder hash is een document niet terug te voeren op regels"


def test_no_allow_rule_hides_a_seeded_value():
    """De harde toets. Een regel die een ingezaaide waarde onderdrukt is per
    definitie fout, en dat is hier automatisch vast te stellen."""
    lijsten = DetectionLists.load(LIJSTEN)
    fout = []
    for type_, waarde in _ingezaaide_waarden():
        for patroon in lijsten.allow.get(type_.upper(), ()):
            if patroon.fullmatch(waarde):
                fout.append((type_, waarde, patroon.pattern))
    assert not fout, f"allow-regels onderdrukken bekende PII: {fout[:5]}"


def test_the_guard_catches_a_rule_that_hides_a_surname(tmp_path):
    """De rem zelf getoetst, want een rem die niets tegenhoudt is een
    versiering.

    `de Vries` komt in het corpus alleen voor ALS deel van "Hendrik de Vries".
    Een regel op de losse achternaam is precies wat er in productie fout gaat,
    en precies wat mijn eerste versie van deze toets liet passeren.
    """
    (tmp_path / "allow.json").write_text(
        json.dumps({"PERSON": [{"patroon": "(?i)^vries$", "reden": "onterecht"}]}),
        encoding="utf-8")
    lijsten = DetectionLists.load(tmp_path)
    betrapt = [
        (t, w) for t, w in _ingezaaide_waarden()
        for p in lijsten.allow.get(t.upper(), ()) if p.fullmatch(w)
    ]
    assert betrapt, "een regel op een losse achternaam kwam er ongezien door"


def test_every_allow_rule_carries_a_reason():
    """Niet alleen bij het laden: ook het bestand zelf moet het kunnen laten
    zien, want dat is wat een mens nakijkt."""
    data = json.loads((LIJSTEN / "allow.json").read_text(encoding="utf-8"))
    for type_, regels in data.items():
        if type_.startswith("_"):
            continue
        for regel in regels:
            assert regel.get("reden", "").strip(), f"{type_}: {regel} zonder reden"


def test_loading_refuses_an_allow_rule_without_a_reason(tmp_path):
    """Geweigerd, niet overgeslagen: half een lijst toepassen is erger dan geen
    lijst, want dan denkt iedereen dat de regel geldt."""
    (tmp_path / "allow.json").write_text('{"PERSON": ["^Jansen$"]}', encoding="utf-8")
    with pytest.raises(ValueError, match="geen reden"):
        DetectionLists.load(tmp_path)


def test_a_deny_rule_may_be_a_bare_string(tmp_path):
    """Deny voegt PII TOE. Dat is de veilige kant op, dus daar is de kale vorm
    goed genoeg."""
    (tmp_path / "deny.json").write_text('{"KENTEKEN": ["\\\\bAA-\\\\d{2}\\\\b"]}',
                                        encoding="utf-8")
    lijsten = DetectionLists.load(tmp_path)
    assert lijsten.deny["KENTEKEN"]


def test_the_rules_are_anchored_and_typed():
    """`^gemeente$` mag geen `gemeente Gooise Meren` raken, en een
    LOCATION-regel geen PERSON. Zonder verankering is een allow-regel een
    zeef in plaats van een uitzondering."""
    lijsten = DetectionLists.load(LIJSTEN)
    from wordsworth.openanonymiser_driver import Entity

    blijft = [
        Entity("LOCATION", "gemeente Bussum", 0, 15, "gliner", 0.9),
        Entity("PERSON", "Locatie", 0, 7, "gliner", 0.9),   # ander type
        Entity("PERSON", "Barbara", 0, 7, "gliner", 0.9),
        Entity("ORGANIZATION", "Jansen Advies", 0, 13, "gliner", 0.9),
    ]
    kept, _ = lijsten.apply("x", blijft)
    assert [e.text for e in kept] == [e.text for e in blijft]


def test_the_list_does_not_exempt_organisations_in_general():
    """Mark, 2026-09-20: bestuursorganen zijn geen PII, want geen natuurlijke
    personen. Dat is iets anders dan "ORGANIZATION is geen PII" — een
    eenmanszaak verstopt zich precies daar. De regels staan daarom op NAAM."""
    lijsten = DetectionLists.load(LIJSTEN)
    from wordsworth.openanonymiser_driver import Entity

    kept, _ = lijsten.apply("x", [
        Entity("ORGANIZATION", "Jansen Advies", 0, 13, "gliner", 0.9),
        Entity("ORGANIZATION", "Boudewijnse Consultancy", 0, 23, "gliner", 0.9),
    ])
    assert len(kept) == 2, "een organisatienaam mag niet als groep vrijgesteld zijn"
