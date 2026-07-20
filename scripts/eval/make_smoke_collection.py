"""Genereer een synthetische mini-testcollectie (pipe-cleaner voor de eval-run).

12 born-digital PDF's over duidelijk onderscheiden gemeentelijke onderwerpen,
6 TSV-queries en TREC-qrels. Doel: de hele keten (ingest-op-qrels-id →
pipeline → OpenSearch → eval-CLI) bewijzen vóór de echte thesis-collectie
erin gaat. Metrics horen hier hoog uit te komen; het gaat om de leiding,
niet om de getallen.
"""
from __future__ import annotations

import io
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

TOPICS = {
    "doc-parkeren-1": "Parkeervergunning aanvragen in het centrum. De parkeervergunning voor bewoners kost veertig euro per jaar en wordt digitaal aangevraagd via het parkeerloket.",
    "doc-parkeren-2": "Handhaving betaald parkeren. De gemeente breidt betaald parkeren uit naar de schilwijken; parkeerwachten controleren met scanauto's op parkeervergunningen.",
    "doc-afval-1": "Afvalinzameling en containers. Restafval wordt om de week opgehaald; grofvuil kan gratis naar de milieustraat of op afspraak aan huis worden opgehaald.",
    "doc-afval-2": "Diftar-tarieven afvalstoffenheffing. De afvalstoffenheffing bestaat uit een vast deel en een bedrag per lediging van de restafvalcontainer.",
    "doc-woo-1": "Woo-verzoek indienen. Een verzoek om publieke informatie op grond van de Wet open overheid kan schriftelijk of digitaal worden ingediend bij de gemeente.",
    "doc-woo-2": "Beslistermijn Woo-verzoeken. De gemeente beslist binnen vier weken op een Woo-verzoek; bij omvangrijke verzoeken kan de termijn met twee weken worden verlengd.",
    "doc-subsidie-1": "Subsidie voor sportverenigingen. Sportverenigingen kunnen jaarlijks subsidie aanvragen voor jeugdactiviteiten en onderhoud van accommodaties.",
    "doc-subsidie-2": "Subsidieregeling energiebesparing. Huiseigenaren krijgen subsidie voor isolatie en zonnepanelen; de regeling loopt tot het budget is uitgeput.",
    "doc-bouwen-1": "Omgevingsvergunning voor een aanbouw. Voor een aanbouw of dakkapel is meestal een omgevingsvergunning nodig; de aanvraag verloopt via het omgevingsloket.",
    "doc-bouwen-2": "Welstandsadvies bij verbouwing. De welstandscommissie toetst bouwplannen aan de welstandsnota, met name in het beschermde stadsgezicht.",
    "doc-verkeer-1": "Verkeersbesluit fietsstraat. De gemeente neemt een verkeersbesluit om de dorpsstraat in te richten als fietsstraat waar de auto te gast is.",
    "doc-verkeer-2": "Snelheidsverlaging naar dertig kilometer per uur. Binnen de bebouwde kom wordt de maximumsnelheid op de meeste wegen verlaagd naar dertig kilometer per uur.",
}

QUERIES = {
    "q1": "parkeervergunning bewoners aanvragen",
    "q2": "grofvuil ophalen milieustraat",
    "q3": "Woo-verzoek beslistermijn",
    "q4": "subsidie isolatie zonnepanelen",
    "q5": "omgevingsvergunning dakkapel aanbouw",
    "q6": "fietsstraat verkeersbesluit",
}

# TREC qrels: query-id 0 doc-id relevantie
QRELS = {
    "q1": {"doc-parkeren-1": 2, "doc-parkeren-2": 1},
    "q2": {"doc-afval-1": 2},
    "q3": {"doc-woo-2": 2, "doc-woo-1": 1},
    "q4": {"doc-subsidie-2": 2},
    "q5": {"doc-bouwen-1": 2, "doc-bouwen-2": 1},
    "q6": {"doc-verkeer-1": 2, "doc-verkeer-2": 1},
}


def pdf_bytes(text: str) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = 800
    for line in [text[i : i + 90] for i in range(0, len(text), 90)]:
        c.drawString(40, y, line)
        y -= 14
    c.showPage()
    c.save()
    return buf.getvalue()


def main() -> None:
    root = Path(__file__).parent / "smoke"
    corpus = root / "corpus"
    corpus.mkdir(parents=True, exist_ok=True)
    for doc_id, text in TOPICS.items():
        (corpus / f"{doc_id}.pdf").write_bytes(pdf_bytes(text))
    with open(root / "queries.tsv", "w", encoding="utf-8") as fh:
        for qid, q in QUERIES.items():
            fh.write(f"{qid}\t{q}\n")
    with open(root / "qrels.txt", "w", encoding="utf-8") as fh:
        for qid, docs in QRELS.items():
            for doc_id, rel in docs.items():
                fh.write(f"{qid} 0 {doc_id} {rel}\n")
    print(f"collectie klaar in {root}: {len(TOPICS)} docs, {len(QUERIES)} queries")


if __name__ == "__main__":
    main()
