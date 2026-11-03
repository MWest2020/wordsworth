"""Dutch particle names as one PERSON span (particle-names-rule, split from #285).

The pilot read of the Gooise Meren dossier found `<first name> ter <last name>`
left readable in a meeting agenda: entity detection split the name or missed it
entirely. This rule matches the whole shape -- gazetteer first name, particle
(`van`, `van der`, `van den`, `de`, `ter`, `ten`), capitalised last name -- as
ONE `PERSON` span, because what identifies a person is the whole name.

Anchored on a first-name gazetteer shipped inside the package, so an
institution of the same shape (`Raad van State`, `Kamer van Koophandel`) never
matches: `Raad` and `Kamer` are not first names. Reversible driver only
(design.md); not a row in `detectors.DETECTORS` (five code paths read that
table and would then misclassify organisation names as PERSON).
"""
from __future__ import annotations

import functools
import importlib.resources
import json
import re
from pathlib import Path

from .openanonymiser_driver import Entity

LAYER = "dutch_particle_name"

# Langste eerst: "van" mag matchen vóór "van der"/"van den" is geprobeerd, maar
# de regex engine backtrackt sowieso als de rest van het patroon dan niet
# aansluit. Deze volgorde is dus leesbaarheid, geen correctheidseis.
PARTICLES = ("van der", "van den", "van", "de", "ter", "ten")

_LAST_NAME = r"[A-ZÀ-Ý][\wà-ÿ'-]*"
_GAZETTEER_PACKAGE = "wordsworth"
_GAZETTEER_RESOURCE = "data/voornamen.json"


def _parse_gazetteer(raw: bytes | str, source: str) -> list[str]:
    try:
        entries = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{source}: not valid JSON") from exc
    if not isinstance(entries, list):
        raise ValueError(f"{source}: expected a list of {{naam, reden}}")
    names: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict) or not str(entry.get("naam", "")).strip():
            raise ValueError(f"{source}: entry without 'naam': {entry!r}")
        naam = entry["naam"]
        if not str(entry.get("reden", "")).strip():
            raise ValueError(f"{source}: entry {naam!r} has no reden")
        names.append(naam)
    return names


def load_gazetteer(path: str | Path | None = None) -> list[str]:
    """The gazetteer's first names. Every entry's `reden` is checked non-empty;
    an entry without one is refused (named in the error), and a missing or
    unreadable file is a hard error -- never an empty list.

    With `path` omitted, reads the file shipped inside the package via
    `importlib.resources`, so what is tested is the path a real install uses.
    `path` is a seam for tests that must point the loader at a missing or
    malformed file.
    """
    if path is None:
        resource = importlib.resources.files(_GAZETTEER_PACKAGE).joinpath(
            _GAZETTEER_RESOURCE)
        source = str(resource)
        if not resource.is_file():
            raise FileNotFoundError(f"gazetteer missing: {source}")
        raw = resource.read_text(encoding="utf-8")
    else:
        file_path = Path(path)
        source = str(file_path)
        if not file_path.is_file():
            raise FileNotFoundError(f"gazetteer missing: {source}")
        raw = file_path.read_text(encoding="utf-8")
    return _parse_gazetteer(raw, source)


@functools.lru_cache(maxsize=1)
def _default_gazetteer() -> tuple[str, ...]:
    return tuple(load_gazetteer())


def build_pattern(first_names: list[str] | tuple[str, ...]) -> re.Pattern[str]:
    """The match pattern for a given set of gazetteer first names.

    A seam so a test can exercise a stub gazetteer without touching the
    package's shipped file."""
    if not first_names:
        raise ValueError("gazetteer: no first names")
    names_alt = "|".join(re.escape(n) for n in sorted(set(first_names),
                                                       key=len, reverse=True))
    particles_alt = "|".join(re.escape(p) for p in PARTICLES)
    return re.compile(rf"\b(?:{names_alt}) (?:{particles_alt}) {_LAST_NAME}\b")


def detect(text: str, first_names: list[str] | tuple[str, ...] | None = None
           ) -> list[Entity]:
    """Every `<first name> <particle> <last name>` span in `text` as ONE
    `PERSON` `Entity` with layer `dutch_particle_name`.

    `first_names` defaults to the package gazetteer (cached: it ships inside
    the package and does not change at runtime); pass an explicit list to test
    against a stub gazetteer instead."""
    names = tuple(first_names) if first_names is not None else _default_gazetteer()
    pattern = build_pattern(names)
    return [Entity("PERSON", m.group(0), m.start(), m.end(), LAYER, 1.0)
            for m in pattern.finditer(text)]
