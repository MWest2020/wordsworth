# SPDX-License-Identifier: MIT
"""Wat een label kan doen om een token, plaatshouder of adres langs de controle
te smokkelen, en dat het niet lukt (topic-labels-llm, review van #433)."""
from __future__ import annotations

import pytest

from wordsworth.topic_label_check import clean, validate

GOEDE_ZIN = "Aanvragen en besluiten over het kappen van bomen."


@pytest.mark.parametrize("tekst", [
    # Tokens: hoofdletters, haken, geplakt, gesplitst.
    "[PERSON:3FA9C2D1] kapt",
    "[person:deadbeef] kapt",
    "person:deadbeef kapt",
    "PERSON3fa9c2d1 kapt",
    "PERSON_3fa9c2d1 kapt",
    "PERSON-3fa9c2d1 kapt",
    "PERSON: 3fa9c2d1 kapt",
    "PERSON: 3fa9 c2d1 kapt",
    "op locatie 3fa9 c2d1",
    "op locatie 9E9D0346",
    # Onzichtbaar of anders geschreven: NFKC en Cf.
    "[PER​SON:3fa9c2d1]",
    "PERSON:3fa9‍c2d1",
    "［PERSON：3fa9c2d1］",
    "Bomen kap",
    "Bomen ⁠kap",
    # Plaatshouders.
    "[Persoon] kapt bomen",
    "[persoon] kapt bomen",
    "[PERSOON-1] kapt bomen",
    "[NAAM 2] kapt bomen",
    "<naam> kapt bomen",
    "{adres} kapt bomen",
    # Adressen.
    "mail j.jansen@example kapt",
    "zie ftp://x",
    "mailto:iemand",
    "gemeente.frl kapt",
    "zie Gooisemeren.Amsterdam",
])
def test_a_smuggled_token_placeholder_or_address_is_not_clean(tekst):
    assert not clean(tekst)
    assert validate({"label": "Bomen", "description": tekst}) is None


@pytest.mark.parametrize("tekst", [
    "Kap van bomen in het centrum",
    "Afvalstoffenheffing 2022",
    "Bezwaar tegen dakkapel",
    "Subsidie voor jeugdactiviteiten",
    "Één bestemmingsplan, vier wijken",
])
def test_ordinary_dutch_stays_clean(tekst):
    assert clean(tekst)


def test_the_label_is_capped_at_eighty_characters():
    lang = " ".join(["Bestemmingsplanwijzigingsprocedure"] * 3)
    assert len(lang) > 80 and len(lang.split()) <= 6
    assert validate({"label": lang, "description": GOEDE_ZIN}) is None
    assert validate({"label": "x" * 80, "description": GOEDE_ZIN}) is not None


def test_the_description_is_capped_at_two_hundred_characters():
    assert validate({"label": "Bomen", "description": "x" * 201}) is None
    assert validate({"label": "Bomen", "description": "x" * 200}) is not None
