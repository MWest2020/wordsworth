# SPDX-License-Identifier: MIT
"""Long synthetic Woo documents with page-level ground truth (synthetic-long-corpus).

Each page is built as its own `Document` (design.md: "One Document per page"),
so the gold carries the page without offset arithmetic: a page's `Document.text`
*is* that page's PDF text, and a `Document.pii()` span is exactly that page's
gold span. The part builders below (cover, table of contents, letter, e-mail
thread, minutes, table) each write one page.

Every planted value is appended through exactly one `Document.pii()` call and
therefore drawn, in `long_corpus_pdf.py`, through exactly one `drawString` run:
a value split across a line break or a table column would fail the extraction
gate (`page_text` inserts a virtual space at a wide gap `drawString` did not
emit). So every line here is kept short enough to need no wrapping, and a
"table" is a column of short `label: value` lines rather than genuinely
columnar cells — simpler, and the same guarantee without a second rendering
path for table geometry.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from .synthetic import (ACHTERNAMEN, STEDEN, STRATEN, VOORNAMEN, Document,
                        bsn_test_range, iban_fake_bank, postcode)

_PART_TITLES = ["Brief", "E-mailwisseling", "Vergadernotulen", "Overzichtstabel"]


def _telefoon(rng: random.Random) -> str:
    """A Dutch mobile number. No detector validates it (unlike BSN/IBAN); it
    is gold for the openanonymiser/GLiNER layer, which does claim this type."""
    return f"06-{rng.randrange(10**8):08d}"


def _header(d: Document, doc_number: str, page: int) -> None:
    """Every page: the document number and the synthetic watermark, never a
    bare 9-digit number or a postcode shape (so they cannot be mistaken for
    planted PII by the deterministic detectors)."""
    d.lit(f"{doc_number}  SYNTHETISCH\n")


def _footer(d: Document, page: int, pages: int) -> None:
    d.lit(f"\npagina {page} van {pages}\n")


def cover_page(doc_id: str, rng: random.Random, pages: int, doc_number: str) -> Document:
    d = Document(f"{doc_id}#p01", "")
    _header(d, doc_number, 1)
    d.lit(f"Gemeente {rng.choice(STEDEN)}\n\n")
    d.lit("OPENBAARMAKING OP GROND VAN DE WET OPEN OVERHEID\n\n")
    d.lit(f"Kenmerk {doc_number}\n")
    d.lit(f"Aantal pagina's: {pages}\n")
    _footer(d, 1, pages)
    return d.check()


def toc_page(doc_id: str, pages: int, doc_number: str) -> Document:
    d = Document(f"{doc_id}#p02", "")
    _header(d, doc_number, 2)
    d.lit("Inhoudsopgave\n\n")
    for i in range(3, pages + 1):
        d.lit(f"{i}. {_PART_TITLES[(i - 3) % len(_PART_TITLES)]}\n")
    _footer(d, 2, pages)
    return d.check()


def letter_page(doc_id: str, rng: random.Random, page: int, pages: int,
                doc_number: str) -> Document:
    d = Document(f"{doc_id}#p{page:02d}", "")
    _header(d, doc_number, page)
    naam = f"{rng.choice(VOORNAMEN)} {rng.choice(ACHTERNAMEN)}"
    d.lit("Geachte heer, mevrouw,\n\n")
    d.lit("Dit besluit betreft ").pii(naam, "PERSON")
    d.lit(", burgerservicenummer ").pii(bsn_test_range(rng), "BSN").lit(".\n")
    d.lit("Correspondentie verloopt via ")
    d.pii(f"{naam.split()[0].lower()}@example.nl", "EMAIL").lit(".\n")
    d.lit("Telefonisch bereikbaar op ").pii(_telefoon(rng), "PHONE_NUMBER").lit(".\n")
    d.lit("Een eventuele nabetaling gaat naar ").pii(iban_fake_bank(rng), "IBAN").lit(".\n")
    d.lit("Correspondentieadres ")
    d.pii(f"{rng.choice(STRATEN)} {rng.randrange(1, 200)}", "LOCATION")
    d.lit(", ").pii(postcode(rng), "POSTCODE").lit(f" {rng.choice(STEDEN)}.\n")
    d.lit("\nHoogachtend,\nhet college van burgemeester en wethouders\n")
    _footer(d, page, pages)
    return d.check()


def email_thread_page(doc_id: str, rng: random.Random, page: int, pages: int,
                      doc_number: str) -> Document:
    d = Document(f"{doc_id}#p{page:02d}", "")
    _header(d, doc_number, page)
    for _ in range(2):
        naam = f"{rng.choice(VOORNAMEN)} {rng.choice(ACHTERNAMEN)}"
        d.lit("Van: ").pii(f"{naam.split()[0].lower()}@example.nl", "EMAIL").lit("\n")
        d.lit("Aan: het secretariaat\n")
        d.lit("Onderwerp: voortgang dossier\n\n")
        d.lit("Beste collega, graag een update van ").pii(naam, "PERSON").lit(".\n\n")
    _footer(d, page, pages)
    return d.check()


def minutes_page(doc_id: str, rng: random.Random, page: int, pages: int,
                 doc_number: str) -> Document:
    d = Document(f"{doc_id}#p{page:02d}", "")
    _header(d, doc_number, page)
    d.lit("Notulen vergadering\n\n")
    d.lit("Aanwezig: ")
    for i in range(3):
        if i:
            d.lit(", ")
        d.pii(f"{rng.choice(VOORNAMEN)} {rng.choice(ACHTERNAMEN)}", "PERSON")
    d.lit(".\n\n")
    d.lit("Besproken: de voortgang van het dossier en de planning voor volgende week.\n")
    _footer(d, page, pages)
    return d.check()


def table_page(doc_id: str, rng: random.Random, page: int, pages: int,
               doc_number: str) -> Document:
    d = Document(f"{doc_id}#p{page:02d}", "")
    _header(d, doc_number, page)
    d.lit("Overzicht\n\n")
    naam = f"{rng.choice(VOORNAMEN)} {rng.choice(ACHTERNAMEN)}"
    d.lit("Naam: ").pii(naam, "PERSON").lit("\n")
    d.lit("BSN: ").pii(bsn_test_range(rng), "BSN").lit("\n")
    d.lit("IBAN: ").pii(iban_fake_bank(rng), "IBAN").lit("\n")
    d.lit("Postcode: ").pii(postcode(rng), "POSTCODE").lit(f" {rng.choice(STEDEN)}\n")
    _footer(d, page, pages)
    return d.check()


_PART_BUILDERS = [letter_page, email_thread_page, minutes_page, table_page]


@dataclass
class LongDocument:
    """One generated document: its pages (1-indexed order), which page
    numbers are scanned, and the query whose only answer is a phrase planted
    on `answer_page`."""

    doc_id: str
    pages: list[Document]
    scanned: set[int]
    answer_page: int
    answer_phrase: str
    query_text: str


def _answer_page(rng: random.Random, pages: int) -> int:
    """At or after page 20, or the last page of a shorter document."""
    return rng.randint(20, pages) if pages >= 20 else pages


def _scanned_pages(rng: random.Random, pages: int, answer_page: int,
                   fraction: float) -> set[int]:
    """A fraction of the pages, rounded down, never page 1 and never the
    answer page (a scanned page has no text layer, so it would silently take
    the query's only answer with it)."""
    n = int(fraction * pages)
    eligible = [p for p in range(2, pages + 1) if p != answer_page]
    return set(rng.sample(eligible, min(n, len(eligible))))


def build_document(doc_id: str, rng: random.Random, pages: int,
                   scanned_fraction: float) -> LongDocument:
    """One long document: its pages, scanned-page selection and query."""
    doc_number = f"WOO-{rng.randint(2020, 2026)}-{rng.randint(0, 9999):04d}"
    answer_page = _answer_page(rng, pages)
    answer_phrase = f"referentie-{doc_id}-{rng.randrange(100000, 999999)}"
    scanned = _scanned_pages(rng, pages, answer_page, scanned_fraction)

    page_docs = [cover_page(doc_id, rng, pages, doc_number)]
    if pages >= 2:
        page_docs.append(toc_page(doc_id, pages, doc_number))
    for page in range(3, pages + 1):
        builder = _PART_BUILDERS[(page - 3) % len(_PART_BUILDERS)]
        page_docs.append(builder(doc_id, rng, page, pages, doc_number))
    page_docs[answer_page - 1].lit(f"\n{answer_phrase}\n")

    return LongDocument(doc_id, page_docs, scanned, answer_page, answer_phrase,
                        answer_phrase)
