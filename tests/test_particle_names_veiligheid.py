# SPDX-License-Identifier: MIT
"""De rem op de voornamen-gazetteer (particle-names-brake, split from #285).

Een gazetteer-entry die ook een gewoon woord is, maakt gewone tekst tot een
`PERSON` en verbergt hem. Dat is een feit dat vóór het uitrollen vaststaat, net
als bij de allow-lijst (`test_allow_list_veiligheid.py`): het evalcorpus weet
wat erin staat, dus elke entry wordt er tegenaan gehouden in plaats van
vertrouwd. Een entry die niet voorkomt telt niet mee als geslaagd -- dat zou
een rem zijn die niets toetst.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

from wordsworth import particle_names

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "gewone_zinnen_nl.txt"


def _corpus_docs(count: int = 300, seed: int = 20260917):
    """`count` gegenereerde documenten uit het evaluatiecorpus, zelfde generator
    en aanpak als `test_allow_list_veiligheid.py`."""
    sys.path.insert(0, str(REPO_ROOT))
    from scripts.eval.generate_ground_truth import TOPICS, build

    rng = random.Random(seed)
    topics = list(TOPICS)
    return [build(f"doc-{i:04d}", topics[i % len(topics)], rng) for i in range(count)]


def test_every_shipped_entry_is_exercised_and_produces_no_false_person():
    docs = _corpus_docs()
    gazetteer = particle_names.load_gazetteer()
    occurs = {naam: 0 for naam in gazetteer}
    fout = []
    for d in docs:
        gouden = {(e["start"], e["end"]) for e in d.entities if e["type"] == "PERSON"}
        for ent in particle_names.detect(d.text, gazetteer):
            voornaam = ent.text.split()[0]
            occurs[voornaam] += 1
            if (ent.start, ent.end) not in gouden:
                fout.append((d.doc_id, voornaam, ent.text))
    niet_ingezaaid = sorted(naam for naam, n in occurs.items() if n == 0)
    assert not niet_ingezaaid, (
        f"nooit voor een partikel en achternaam ingezaaid: {niet_ingezaaid}")
    assert not fout, f"valse PERSON-detectie buiten het gouden antwoord: {fout[:5]}"


def _fixture_lines(path: Path = FIXTURE) -> list[list[str]]:
    regels = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.strip():
            regels.append(raw.split("\t"))
    return regels


def _particle_in_fullname(fullname_template: str) -> str:
    rest = fullname_template.removeprefix("{naam} ")
    for particle in particle_names.PARTICLES:
        if rest.startswith(particle + " "):
            return particle
    raise ValueError(f"geen bekend partikel in {fullname_template!r}")


def _missing_particles(lines: list[list[str]], naam: str) -> list[str]:
    """Partikels zonder een PERSON-zin in `lines` waarvan de detectie ook echt
    optreedt."""
    gevonden = set()
    for parts in lines:
        if parts[0] != "PERSON":
            continue
        _, zin_template, fullname_template = parts
        particle = _particle_in_fullname(fullname_template)
        zin = zin_template.format(naam=naam)
        volledige_naam = fullname_template.format(naam=naam)
        ents = particle_names.detect(zin, [naam])
        if any(e.text == volledige_naam for e in ents):
            gevonden.add(particle)
    return [p for p in particle_names.PARTICLES if p not in gevonden]


def test_every_particle_has_a_person_sentence_in_the_fixture_whose_detection_occurs():
    naam = particle_names.load_gazetteer()[0]
    ontbreekt = _missing_particles(_fixture_lines(), naam)
    assert not ontbreekt, f"geen werkende PERSON-zin voor partikel: {ontbreekt}"


def test_the_coverage_guard_catches_a_particle_with_no_person_sentence():
    """De bewaker zelf getoetst: een fixture zonder PERSON-zin voor een partikel
    moet dát partikel met naam terugmelden."""
    naam = particle_names.load_gazetteer()[0]
    weg = particle_names.PARTICLES[0]
    zonder = [parts for parts in _fixture_lines()
              if not (parts[0] == "PERSON" and _particle_in_fullname(parts[2]) == weg)]
    assert _missing_particles(zonder, naam) == [weg]
