# SPDX-License-Identifier: MIT
"""The six long-corpus part builders (cover, table of contents, letter,
e-mail thread, minutes, table), each returning a `Document` -- one page's
worth of planted text. Not yet wrapped in a header/footer (`long_corpus.py`
does that) and not yet drawn (`long_corpus_pdf.py` does that).

Every value is one `.pii()`/`.lit()` call, so it ends up as exactly one
character run; the page drawer (`long_corpus_pdf.py`) turns one line of text
into one `drawString` call and one tab-separated cell into one more, never
splitting a planted value across either. A value repeated on the same page
would be found twice in the page's extracted text, which the generator
treats as a hard error (`long_corpus._extract_gold`) -- `_unique` below rules
that out for the parts that plant more than one value of the same type.
"""
from __future__ import annotations

import random

from .synthetic import (ACHTERNAMEN, STEDEN, STRATEN, VOORNAMEN, Document,
                        bsn_test_range, iban_fake_bank, postcode)

ONDERWERPEN = [
    "de aanvraag van de omgevingsvergunning",
    "het Woo-verzoek over het parkeerbeleid",
    "de subsidieaanvraag voor de sportvereniging",
    "het verkeersbesluit voor de fietsstraat",
]


def _naam(rng: random.Random) -> str:
    return f"{rng.choice(VOORNAMEN)} {rng.choice(ACHTERNAMEN)}"


def _telefoon(rng: random.Random) -> str:
    return f"06-{rng.randrange(10000000, 99999999)}"


def _email(naam: str) -> str:
    voor, _, achter = naam.partition(" ")
    return f"{voor.lower()}.{achter.lower().replace(' ', '')}@example.nl"


def _unique(rng: random.Random, used: set[str], fn) -> str:
    """`fn(rng)` until it draws a value not already on this page -- the gate
    in `long_corpus._extract_gold` wants every value exactly once."""
    while True:
        value = fn(rng)
        if value not in used:
            used.add(value)
            return value


def _postcode(rng: random.Random) -> str:
    """`synthetic.postcode`, redrawn when it contains "11": two adjacent "1"s
    read to `pdf_text.page_text`'s gap heuristic as a missing word space (see
    `synthetic.bsn_test_range`). `postcode` itself stays untouched -- it is
    also the 500-document corpus's generator, and changing it would change
    that corpus's values for the same seed."""
    while True:
        value = postcode(rng)
        if "11" not in value:
            return value


def _adres(rng: random.Random) -> str:
    """Street + house number, the number redrawn when it contains "11" (see
    `_postcode`); the street name carries no digits, so only the number can
    trigger the gap heuristic."""
    straat = rng.choice(STRATEN)
    while True:
        nummer = rng.randrange(1, 200)
        if "11" not in str(nummer):
            return f"{straat} {nummer}"


def build_cover(rng: random.Random, doc_number: str) -> Document:
    d = Document(doc_number, "")
    naam = _naam(rng)
    d.lit("WOO-BESLUIT\n\n")
    d.lit(f"Gemeente {rng.choice(STEDEN)}\n")
    d.lit(f"Betreft: {rng.choice(ONDERWERPEN)}\n\n")
    d.lit("Aan:\n")
    d.pii(naam, "PERSON").lit("\n")
    d.pii(_adres(rng), "LOCATION").lit("\n")
    d.pii(_postcode(rng), "POSTCODE").lit(f" {rng.choice(STEDEN)}\n")
    return d.check()


def build_toc(rng: random.Random, doc_number: str) -> Document:
    d = Document(doc_number, "")
    d.lit("INHOUDSOPGAVE\n\n")
    for i, sectie in enumerate(
            ["Aanleiding", "Beoordeling", "Correspondentie", "Besluit", "Bijlagen"],
            start=1):
        d.lit(f"{i}. {sectie}\n")
    return d.check()


def build_letter(rng: random.Random, doc_number: str) -> Document:
    d = Document(doc_number, "")
    naam = _naam(rng)
    geboortedatum = (f"{rng.randrange(1, 29):02d}-{rng.randrange(1, 13):02d}-"
                     f"{rng.randrange(1940, 2006)}")
    d.lit(f"Geachte heer, mevrouw {rng.choice(ACHTERNAMEN)},\n\n")
    d.lit("Dit besluit betreft ").pii(naam, "PERSON")
    d.lit(", geboren op ").unlabelled(geboortedatum, "DOB")
    d.lit(", burgerservicenummer ").pii(bsn_test_range(rng), "BSN").lit(".\n")
    if rng.random() < 0.5:
        d.lit("Correspondentie verloopt via telefoon ")
        d.unlabelled(_telefoon(rng), "PHONE").lit(".\n")
    if rng.random() < 0.5:
        d.lit("Een eventuele nabetaling gaat naar ")
        d.pii(iban_fake_bank(rng), "IBAN").lit(".\n")
    d.lit("\nHoogachtend,\nhet college van burgemeester en wethouders\n")
    return d.check()


def build_email_thread(rng: random.Random, doc_number: str) -> Document:
    d = Document(doc_number, "")
    d.lit("E-MAILCORRESPONDENTIE\n\n")
    used_emails: set[str] = set()
    for _ in range(3):
        van = _unique(rng, used_emails, lambda r: _email(_naam(r)))
        naar = _unique(rng, used_emails, lambda r: _email(_naam(r)))
        d.lit("Van: ").pii(van, "EMAIL").lit("\n")
        d.lit("Aan: ").pii(naar, "EMAIL").lit("\n")
        d.lit(f"Onderwerp: {rng.choice(ONDERWERPEN)}\n")
        d.lit("Bericht: zie bijlage voor de stukken.\n\n")
    return d.check()


def build_minutes(rng: random.Random, doc_number: str) -> Document:
    d = Document(doc_number, "")
    d.lit("NOTULEN VERGADERING\n\n")
    d.lit("Aanwezig:\n")
    used_names: set[str] = set()
    for _ in range(4):
        d.pii(_unique(rng, used_names, _naam), "PERSON").lit("\n")
    d.lit(f"\nAgendapunt: {rng.choice(ONDERWERPEN)}\n")
    d.lit("Besluit: akkoord onder voorbehoud van definitieve vaststelling.\n")
    return d.check()


def build_table(rng: random.Random, doc_number: str) -> Document:
    d = Document(doc_number, "")
    d.lit("Zaaknummer\tNaam\tBSN\tPostcode\n")
    used_names: set[str] = set()
    used_bsns: set[str] = set()
    used_postcodes: set[str] = set()
    for i in range(5):
        d.lit(f"Z-{i:03d}\t")
        d.pii(_unique(rng, used_names, _naam), "PERSON").lit("\t")
        d.pii(_unique(rng, used_bsns, bsn_test_range), "BSN").lit("\t")
        d.pii(_unique(rng, used_postcodes, _postcode), "POSTCODE").lit("\n")
    return d.check()
