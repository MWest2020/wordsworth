# SPDX-License-Identifier: MIT
"""The demo's documents: synthetic text from `wordsworth.eval.synthetic`, one PDF each.

Every value is invented by the generator (an elfproef-valid BSN that belongs to
nobody, a mod-97 IBAN on a test bank code, names from a fixed list), and every
page says on its first line that it is synthetic. Same seed, same documents: the
content is a function of SEED and COUNT, so two runs show the same dossier.
"""
from __future__ import annotations

import io
import random
import textwrap

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from wordsworth.eval.synthetic import (ACHTERNAMEN, STEDEN, STRATEN, VOORNAMEN,
                                       Document, bsn, iban, postcode)

SEED = 20261113
COUNT = 30
DOSSIER = "Demo-dossier (synthetisch)"
BANNER = "SYNTHETISCH DEMODOCUMENT - geen echte persoon, geen echte zaak"

# Six subjects, five documents each: enough for the topic clustering to find
# groups (its minimum size is three) and for a question to have a right answer.
SUBJECTS = {
    "parkeren": [
        "Het college verleent een parkeervergunning voor bewoners in de "
        "vergunningszone van de binnenstad.",
        "Parkeerwachten controleren de parkeervergunning met een scanauto; een "
        "tweede vergunning per adres wordt niet verleend.",
    ],
    "afval": [
        "De afvalstoffenheffing bestaat uit een vast deel en een bedrag per lediging "
        "van de restafvalcontainer.",
        "Grofvuil kan op afspraak worden opgehaald of gratis naar de milieustraat "
        "worden gebracht.",
    ],
    "bouwen": [
        "De omgevingsvergunning voor het plaatsen van een dakkapel is getoetst aan "
        "de welstandsnota.",
        "De welstandscommissie adviseert positief over de uitbouw aan de "
        "achterzijde van de woning.",
    ],
    "subsidie": [
        "De subsidie voor de sportvereniging is bedoeld voor jeugdactiviteiten en "
        "onderhoud van de accommodatie.",
        "De vereniging legt na afloop van het seizoen verantwoording af over de "
        "besteding van de subsidie.",
    ],
    "bezwaar": [
        "Het bezwaarschrift is behandeld op een hoorzitting van de "
        "bezwaarschriftencommissie.",
        "De commissie adviseert het bezwaar ongegrond te verklaren; het bestreden "
        "besluit blijft in stand.",
    ],
    "wmo": [
        "Na een keukentafelgesprek is een maatwerkvoorziening huishoudelijke hulp "
        "toegekend op grond van de Wmo.",
        "De eigen bijdrage voor de maatwerkvoorziening wordt door het CAK "
        "vastgesteld.",
    ],
}


def build(n: int, subject: str, rng: random.Random) -> Document:
    """One letter about `subject`, with its personal data recorded as it is written."""
    d = Document(f"demo-{n:03d}", subject)
    stad = rng.choice(STEDEN)
    naam = f"{rng.choice(VOORNAMEN)} {rng.choice(ACHTERNAMEN)}"
    d.lit(f"{BANNER}\nGemeente {stad}\nKenmerk {d.doc_id}\n\nGeachte heer, mevrouw,\n\n")
    for sentence in SUBJECTS[subject]:
        d.lit(sentence).lit("\n")
    d.lit("\nDit besluit betreft ").pii(naam, "PERSON")
    d.lit(", burgerservicenummer ").pii(bsn(rng), "BSN").lit(".\n")
    if rng.random() < 0.5:
        d.lit("Correspondentie verloopt via ")
        d.pii(f"{naam.split()[0].lower()}@example.nl", "EMAIL").lit(".\n")
    if rng.random() < 0.4:
        d.lit("Een eventuele nabetaling gaat naar ").pii(iban(rng), "IBAN").lit(".\n")
    if rng.random() < 0.4:
        d.lit("Betrokkene woont aan de ")
        d.pii(f"{rng.choice(STRATEN)} {rng.randrange(1, 200)}", "LOCATION")
        d.lit(", postcode ").pii(postcode(rng), "POSTCODE").lit(f" {stad}.\n")
    d.lit("\nHoogachtend,\nhet college van burgemeester en wethouders\n")
    return d.check()


def documents(count: int = COUNT, seed: int = SEED) -> list[Document]:
    rng = random.Random(seed)
    subjects = list(SUBJECTS)
    return [build(i + 1, subjects[i % len(subjects)], rng) for i in range(count)]


def filename(d: Document) -> str:
    return f"{d.doc_id}-{d.topic}.pdf"


def _lines(d: Document, width: int = 90) -> list[str]:
    """Wrap the text without ever breaking inside a recorded value.

    A name split over two lines is two strings in the PDF's text layer, and the
    box map cannot draw one box over both. So the spaces inside a value are
    protected while wrapping and restored after.
    """
    keep = "\x00"
    text = d.text
    for e in sorted(d.entities, key=lambda e: e["start"], reverse=True):
        value = text[e["start"]:e["end"]].replace(" ", keep)
        text = text[:e["start"]] + value + text[e["end"]:]
    out: list[str] = []
    for paragraph in text.split("\n"):
        wrapped = textwrap.wrap(paragraph, width, break_long_words=False,
                                break_on_hyphens=False) or [""]
        out.extend(line.replace(keep, " ") for line in wrapped)
    return out


def render(d: Document) -> bytes:
    """A born-digital PDF of the letter: a real text layer, one page."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4, invariant=1)
    c.setFont("Helvetica", 10)
    y = 800
    for line in _lines(d):
        c.drawString(60, y, line)
        y -= 14
    c.showPage()
    c.save()
    return buf.getvalue()


def render_scan(d: Document) -> bytes:
    """The same letter as a scan would arrive: a page without a text layer."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4, invariant=1)
    for i, _line in enumerate(_lines(d)):
        c.rect(60, 800 - 14 * i, 300 + (i * 37) % 150, 8, fill=1)
    c.showPage()
    c.save()
    return buf.getvalue()


def seeded_values(docs: list[Document]) -> dict[str, str]:
    """value -> type, for the types the deterministic detectors do not cover."""
    found: dict[str, str] = {}
    for d in docs:
        for e in d.entities:
            if e["type"] in ("PERSON", "LOCATION", "POSTCODE"):
                found[d.text[e["start"]:e["end"]]] = e["type"]
    return found
