# SPDX-License-Identifier: MIT
"""De rem op de voornamen-gazetteer, fixture-helft (particle-names-brake, split
from #285). Elke zin in `tests/fixtures/gewone_zinnen_nl.txt` zegt zelf wat hij
verwacht -- een `PERSON`-zin de volledige naam die de regel moet dekken, een
`GEEN`-zin dat de regel niets mag vinden -- zodat deze toets de volledige naam
niet zelf met een partikel-scan hoeft te vinden; diezelfde scan zou een bug in
de regel kopiëren naar de toets.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest

from wordsworth import particle_names
from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import InMemoryMappingStore
from wordsworth.pseudonymizer import ReversibleAnonymizer

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "gewone_zinnen_nl.txt"
_GAZETTEER = particle_names.load_gazetteer()


def _read_fixture(path: Path = FIXTURE) -> list[list[str]]:
    """Elke regel moet een expectation hebben (`PERSON` of `GEEN`); een
    `PERSON`-regel moet de derde kolom (de volledige naam) hebben."""
    regels = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        parts = raw.split("\t")
        if parts[0] not in ("PERSON", "GEEN"):
            raise ValueError(f"regel zonder gestelde expectation: {raw!r}")
        if parts[0] == "PERSON" and len(parts) != 3:
            raise ValueError(f"PERSON-regel zonder volledige naam (derde kolom): {raw!r}")
        if parts[0] == "GEEN" and len(parts) != 2:
            raise ValueError(f"GEEN-regel met een onverwachte kolom: {raw!r}")
        regels.append(parts)
    return regels


@pytest.mark.parametrize("naam", _GAZETTEER)
def test_every_shipped_entry_over_every_fixture_sentence(naam):
    for parts in _read_fixture():
        soort, zin_template = parts[0], parts[1]
        zin = zin_template.format(naam=naam)
        ents = particle_names.detect(zin, [naam])
        if soort == "PERSON":
            volledige_naam = parts[2].format(naam=naam)
            assert any(e.text == volledige_naam for e in ents), (
                f"{naam}: geen PERSON voor {volledige_naam!r} in {zin!r}")
            r = ReversibleAnonymizer(InMemoryKeyProvider(), InMemoryMappingStore(),
                                      detect=lambda t: []).anonymize(zin)
            assert volledige_naam not in r.text, (
                f"{naam}: {volledige_naam!r} nog leesbaar na anonimiseren: {r.text!r}")
        else:
            assert ents == [], f"{naam}: onterechte PERSON in {zin!r}: {ents}"


def test_a_line_without_a_stated_expectation_fails(tmp_path):
    bestand = tmp_path / "onbekend.txt"
    bestand.write_text("ONBEKEND\tiets over {naam}.\n", encoding="utf-8")
    with pytest.raises(ValueError, match="expectation"):
        _read_fixture(bestand)


def test_a_person_line_without_a_third_column_fails(tmp_path):
    bestand = tmp_path / "zonder_naam.txt"
    bestand.write_text("PERSON\t{naam} van Dijk kwam langs.\n", encoding="utf-8")
    with pytest.raises(ValueError, match="volledige naam"):
        _read_fixture(bestand)


# --- Negatieve controles: de rem moet ook echt tanden hebben --------------


def test_a_stub_gazetteer_holding_ton_would_be_caught_as_a_person():
    """`Ton` staat met opzet niet in de gazetteer (test_particle_names.py):
    het is ook een gewoon hoofdlettervolgorde-woord. Deze toets laat zien dat
    stáp 1's uitsluiting (`detect(zin) == []`) zou falen als `Ton` wél
    verscheept was -- het bewijs dat de fixture-toets hierboven, mocht zoiets
    gebeuren, het ook werkelijk opmerkt."""
    zin = "Ton van der Berg kwam langs."
    ents = particle_names.detect(zin, ["Ton"])
    assert ents and ents[0].text == "Ton van der Berg", (
        "een gestubde entry 'Ton' werd niet als PERSON opgemerkt")


def _corpus_docs(count: int = 300, seed: int = 20260917):
    sys.path.insert(0, str(REPO_ROOT))
    from scripts.eval.generate_ground_truth import TOPICS, build

    rng = random.Random(seed)
    topics = list(TOPICS)
    return [build(f"doc-{i:04d}", topics[i % len(topics)], rng) for i in range(count)]


def test_a_stub_entry_the_corpus_never_emits_fails_the_occurrence_check():
    """`Zzyzx` komt de generator nooit uit. Dit laat zien dat de
    bezettingstoets in `test_particle_names_veiligheid.py` zo'n entry
    terecht als "niet ingezaaid" zou afkeuren, in plaats van hem voor lief te
    nemen bij gebrek aan een valse `PERSON`."""
    docs = _corpus_docs()
    gevonden = any(particle_names.detect(d.text, ["Zzyzx"]) for d in docs)
    assert not gevonden, "Zzyzx hoort nooit voor een partikel en achternaam te staan"


def test_neither_brake_test_file_writes_to_the_shipped_gazetteer():
    """Een rem die treft, faalt en noemt de entry -- hij bewerkt
    `voornamen.json` nooit. Statisch getoetst: geen regel in deze twee
    bestanden combineert dat pad met een schrijfactie."""
    hier = Path(__file__).resolve().parent
    for bestand in ("test_particle_names_veiligheid.py", "test_particle_names_zinnen.py"):
        for regel in (hier / bestand).read_text(encoding="utf-8").splitlines():
            if "voornamen.json" in regel:
                assert "write" not in regel.lower(), (
                    f"{bestand}: schrijfactie op voornamen.json: {regel!r}")
