# SPDX-License-Identifier: MIT
"""Generate an evaluation corpus whose answer we know (ground-truth-corpus).

Measurement 01 ran on 31 documents. That is enough to find a bug and too little
to carry a percentage. This writes ~500 documents plus, from the same run:

  gold.jsonl    the PII spans, for `python -m wordsworth.eval.pii_run`
  queries.tsv   \\  the known ranking, for `python -m wordsworth.eval.run`
  qrels.txt     /
  manifest.json what was seeded, so a measurement can be checked against it

One generation, two evaluations, the same documents. Two corpora would give two
numbers that cannot be held next to each other.

Read the caveat in the manifest before quoting any score: this text was written
by us and is more regular than administrative reality. A score here is a lower
bound for the machinery, not a prediction for production.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from wordsworth.eval.synthetic import (ACHTERNAMEN, STEDEN, STRATEN, VOORNAMEN,
                                       Document, bsn, iban, postcode)

# Each topic is a query plus the vocabulary that makes a document about it.
TOPICS = {
    "parkeren": ("parkeervergunning bewoners",
                 "Het college besloot over een parkeervergunning voor bewoners in de "
                 "vergunningszone; parkeerwachten controleren met een scanauto."),
    "afval": ("afvalstoffenheffing diftar",
              "De afvalstoffenheffing kent een vast deel en een bedrag per lediging "
              "van de restafvalcontainer; grofvuil gaat naar de milieustraat."),
    "woo": ("beslistermijn woo-verzoek",
            "Op dit Woo-verzoek om publieke informatie is binnen de beslistermijn van "
            "vier weken besloten; de termijn is eenmaal verlengd."),
    "subsidie": ("subsidie sportvereniging jeugd",
                 "De subsidie voor de sportvereniging betreft jeugdactiviteiten en "
                 "onderhoud van de accommodatie."),
    "bouwen": ("omgevingsvergunning dakkapel",
               "De omgevingsvergunning voor een dakkapel is getoetst door de "
               "welstandscommissie aan de welstandsnota."),
    "verkeer": ("verkeersbesluit fietsstraat",
                "Het verkeersbesluit richt de straat in als fietsstraat waar de auto "
                "te gast is; de maximumsnelheid gaat naar dertig kilometer per uur."),
    "uitkering": ("bijstandsuitkering participatiewet",
                  "De bijstandsuitkering op grond van de Participatiewet is herzien; "
                  "het recht op de uitkering blijft bestaan."),
    "bezwaar": ("bezwaarschrift hoorzitting",
                "Het bezwaarschrift is behandeld op een hoorzitting van de "
                "bezwaarschriftencommissie; het bestreden besluit blijft in stand."),
    "handhaving": ("last onder dwangsom handhaving",
                   "De last onder dwangsom is opgelegd na constatering van de "
                   "overtreding door de toezichthouder."),
    "wmo": ("wmo maatwerkvoorziening huishoudelijke hulp",
            "De maatwerkvoorziening huishoudelijke hulp is op grond van de Wmo "
            "toegekend na een keukentafelgesprek."),
}
GESLACHT = ["man", "vrouw"]


def build(doc_id: str, topic: str, rng: random.Random) -> Document:
    """One document, its PII spans and the types it carries in the clear."""
    d = Document(doc_id, topic)
    _, body = TOPICS[topic]
    naam = f"{rng.choice(VOORNAMEN)} {rng.choice(ACHTERNAMEN)}"

    d.lit(f"Gemeente {rng.choice(STEDEN)}\nKenmerk {doc_id}\n\nGeachte heer, mevrouw,\n\n")
    d.lit("Betreft: ").lit(body).lit("\n\nDit besluit betreft ").pii(naam, "PERSON")
    d.lit(", burgerservicenummer ").pii(bsn(rng), "BSN").lit(".\n")

    if rng.random() < 0.55:
        d.lit("Correspondentie verloopt via ")
        d.pii(f"{naam.split()[0].lower()}@example.nl", "EMAIL").lit(".\n")
    if rng.random() < 0.45:
        d.lit("Een eventuele nabetaling gaat naar ").pii(iban(rng), "IBAN").lit(".\n")

    # The quasi-identifier, seeded deliberately: gender + year of birth + postcode.
    # Only the postcode has a detector; the other two are carried but not gold.
    heeft_combinatie = rng.random() < 0.40
    if heeft_combinatie:
        d.lit("Betrokkene is ").unlabelled(rng.choice(GESLACHT), "GENDER")
        d.lit(", geboren in ").unlabelled(str(rng.randrange(1940, 2006)), "DATE")
        # A RESIDENTIAL address is PII, and gold. Mark's decision 2026-09-22:
        # "street addresses should be PII unless specified". Until then this was
        # seeded with .lit() -- ordinary text -- so a detector that found it was
        # charged with a false positive for being right. Street and house number
        # are ONE span, because that is what identifies a person: the street on
        # its own is a place, the number on its own is nothing.
        d.lit(", woonachtig ")
        d.pii(f"{rng.choice(STRATEN)} {rng.randrange(1, 200)}", "LOCATION")
        d.lit(", ").pii(postcode(rng), "POSTCODE").lit(".\n")

    # The hard cases measurement 01 actually met — seeded, not invented.
    if rng.random() < 0.25:
        # "Unless specified": an organisation's contact address is not a person's
        # home. A postcode behind "Postbus" must NOT be found, and neither must
        # the box number -- it is in the text and deliberately not in the gold.
        # This is the counter-case to the residential address above; without it
        # the corpus would reward a detector that redacts every address it sees.
        d.lit(f"Postbus {rng.randrange(100, 9999)}, {postcode(rng)} "
              f"{rng.choice(STEDEN)}\n")
    if rng.random() < 0.15:
        # Text arriving with something token-shaped in it. Not PII, and a
        # detector that treats it as PII is inventing a finding.
        d.lit("In het dossier staat de aanduiding [ZAAK:12ab34cd] vermeld.\n")

    d.lit("\nHoogachtend,\nhet college van burgemeester en wethouders\n")
    return d.check()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Generate a corpus with known answers")
    ap.add_argument("outdir", type=Path)
    ap.add_argument("--count", type=int, default=500)
    ap.add_argument("--seed", type=int, default=20260917)
    args = ap.parse_args(argv)

    rng = random.Random(args.seed)
    topics = list(TOPICS)
    docs = [build(f"doc-{i:04d}", topics[i % len(topics)], rng)
            for i in range(args.count)]

    out = args.outdir
    (out / "documents").mkdir(parents=True, exist_ok=True)
    for d in docs:
        (out / "documents" / f"{d.doc_id}.txt").write_text(d.text, encoding="utf-8")
    (out / "gold.jsonl").write_text(
        "".join(json.dumps(d.gold(), ensure_ascii=False) + "\n" for d in docs),
        encoding="utf-8")
    (out / "queries.tsv").write_text(
        "".join(f"q-{t}\t{TOPICS[t][0]}\n" for t in topics), encoding="utf-8")
    # Every document is judged for every query. A document left out of qrels is
    # indistinguishable from one judged irrelevant, and the metrics differ.
    (out / "qrels.txt").write_text(
        "".join(f"q-{t} 0 {d.doc_id} {1 if d.topic == t else 0}\n"
                for t in topics for d in docs), encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps({
        "documents": len(docs),
        "seed": args.seed,
        "entities": sum(len(d.entities) for d in docs),
        "entities_per_type": {t: sum(1 for d in docs for e in d.entities
                                     if e["type"] == t)
                              for t in sorted({e["type"] for d in docs
                                               for e in d.entities})},
        "documents_carrying_gender_date_postcode": sum(
            1 for d in docs if {"GENDER", "DATE", "POSTCODE"} <= d.types),
        "caveat": ("Synthetic. Written by us and more regular than administrative "
                   "reality: a score here is a lower bound for the machinery, not a "
                   "prediction for production text. GENDER and a bare year of birth "
                   "are carried but deliberately not gold — no detector emits them, "
                   "and scoring a detector on what it never claimed to find is a "
                   "measurement about us, not about it."),
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(docs)} documents -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
