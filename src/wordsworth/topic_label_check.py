# SPDX-License-Identifier: MIT
"""Is dit antwoord van het model een bruikbaar label? (topic-labels-llm)

Afwijzen, niet repareren: een ingekort of opgeschoond label is een label dat
het model niet schreef. Strenger dan nodig is hier goedkoop, want een
afgewezen label kost alleen dat het onderwerp zijn termen houdt (en een mens
kan het een naam geven); een doorgelaten token staat op elk scherm waar de
reveal-poort nooit kijkt.

Wat een token kan nadoen, en dus wordt afgewezen:

- tekst die verandert onder NFKC of door het weghalen van onzichtbare tekens
  (categorie Cf): een breedteteken of een zero-width space in een token
  ontloopt elk patroon, en een label hoort geen van beide te bevatten;
- type en id, in welke hoofdletters ook, met of zonder haken, aan elkaar
  geplakt of met spaties in de id: `[person:deadbeef]`, `PERSON3fa9c2d1`,
  `PERSON: 3fa9 c2d1`;
- een kale id van acht hex-tekens met minstens één cijfer (`9e9d0346`, ook
  `9e9d 0346`); zonder cijfer-eis is "deadbeef" een id en "afgedaan" bijna;
- een plaatshouder tussen `[]`, `<>` of `{}`, ook met kleine letters, cijfers
  of een streepje: `[Persoon]`, `[PERSOON-1]`, `<naam>`;
- alles wat een adres kan zijn: `@`, `://`, `mailto:`, en elk `woord.tld`.
"""
from __future__ import annotations

import re
import unicodedata

LABEL_WORDS = 6
LABEL_CHARS = 80
DESCRIPTION_CHARS = 200

_HEX8 = r"[0-9a-f](?:\s?[0-9a-f]){7}"
#: Type plus id: met dubbelepunt (en eventueel spatie), streepje, liggend
#: streepje, of direct aan elkaar.
_TYPED = re.compile(rf"(?i)[a-z_]+(?::\s*|[-_]?){_HEX8}(?![0-9a-z])")
_BARE = re.compile(rf"(?i)(?<![0-9a-z]){_HEX8}(?![0-9a-z])")
_PLACEHOLDER = re.compile(r"(?i)[\[<{]\s*[a-z_][a-z0-9_\-\s]*[\]>}]")
_ADDRESS = re.compile(r"(?i)@|://|mailto:|\b[a-z0-9-]+\.[a-z]{2,}\b")


def _invisible_or_odd(text: str) -> bool:
    plain = "".join(c for c in unicodedata.normalize("NFKC", text)
                    if unicodedata.category(c) != "Cf")
    return plain != text


def _token(text: str) -> bool:
    if _TYPED.search(text):
        return True
    return any(re.search(r"\d", m.group(0)) for m in _BARE.finditer(text))


def clean(text: str) -> bool:
    """Geen token, geen plaatshouder, geen adres, niets onzichtbaars."""
    return not (_invisible_or_odd(text) or _token(text)
                or _PLACEHOLDER.search(text) or _ADDRESS.search(text))


def validate(answer: object) -> tuple[str, str] | None:
    """(label, beschrijving) als het antwoord deugt, anders None."""
    if not isinstance(answer, dict):
        return None
    label, description = answer.get("label"), answer.get("description")
    if not isinstance(label, str) or not isinstance(description, str):
        return None
    label, description = label.strip(), description.strip()
    if (len(label.splitlines()) != 1 or len(label) > LABEL_CHARS
            or not 1 <= len(label.split()) <= LABEL_WORDS):
        return None
    if len(description.splitlines()) != 1 or len(description) > DESCRIPTION_CHARS:
        return None
    return (label, description) if clean(label) and clean(description) else None
