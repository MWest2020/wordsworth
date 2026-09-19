# SPDX-License-Identifier: MIT
"""Samenvattingen per document (samenvattingen).

Een samenvatting is de enige tekst in dit systeem die **niet terug te voeren is
op iets dat is opgeslagen.** Het fragment op de zoekpagina is een citaat: je
kunt het terugvinden in de gepseudonimiseerde tekst. Een samenvatting is een
bewering, geschreven door een taalmodel. Daarom draagt hij zijn herkomst mee —
welk model, wanneer — en staat hij naast het citaat en niet ervoor in de plaats.

**De tokens gaan eruit, ná het genereren.** Een citaat kan geen token verzinnen;
gegenereerde tekst wel. Tokens lossen op via een globale mappingstore, dus een
verzonnen `[PERSOON:aabbccdd]` is geen onzin — het is iemand, alleen niet iemand
uit dit document. Een samenvatting die hem draagt koppelt een vreemde aan dit
stuk, en een onthulling daarop levert de klare naam van die vreemde binnen een
grant die op dít document gescoped is. Dat is het gat dat
`neutralise_foreign_tokens` aan de invoerkant dichtzet, hier aan de uitvoerkant.

De prompt vraagt het model óók om geen tokens over te nemen. Dat is een verzoek;
het filteren hieronder is de garantie, en alleen op die tweede staat een test.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from .generator import GenerationError, Generator
from .models import DocumentSummary
from .pipeline import get_anonymized_text
from .pseudonymizer import without_tokens

_SPATIES = re.compile(r"\s+")


@dataclass(frozen=True)
class Made:
    """De noemer van één berekening.

    Zonder deze vier leest "twaalf samenvattingen" als een uitspraak over het
    hele dossier, ook als er dertig documenten in zitten.
    """

    seen: int
    made: int
    skipped: int      # had er al een
    failed: int       # het model gaf niets bruikbaars
    without_text: int  # nooit door de straat gekomen


def clean(generated: str) -> str:
    """De tekst zoals hij opgeslagen wordt: zonder tokens, zonder dubbele witruimte.

    Leeg terug betekent: dit is geen samenvatting. De aanroeper slaat dan niets
    op — een placeholder die eruitziet als inhoud is erger dan een leeg veld,
    want hij wordt gelezen als de samenvatting van een document dat niemand
    heeft samengevat.
    """
    return _SPATIES.sub(" ", without_tokens(generated or "")).strip()


def for_document(session: Session, generator: Generator, document_id: UUID,
                 model: str) -> DocumentSummary | None:
    """Maak en bewaar één samenvatting, of geef None als dat niet lukt."""
    tekst = get_anonymized_text(session, document_id)
    if not tekst:
        return None
    try:
        rauw = generator.summarise(tekst)
    except GenerationError:
        # Een mislukte generatie is geen samenvatting. Geen halve tekst, geen
        # foutmelding die als inhoud op een scherm belandt.
        return None
    samenvatting = clean(rauw)
    if not samenvatting:
        return None
    rij = DocumentSummary(document_id=document_id, text=samenvatting, model=model)
    session.merge(rij)
    session.flush()
    return rij


def compute(session: Session, generator: Generator, document_ids,
            model: str) -> Made:
    """Maak wat er nog niet is. Bestaande samenvattingen blijven staan.

    Opnieuw laten draaien doet het werk dus niet opnieuw — bij een taalmodel is
    dat geen optimalisatie maar het verschil tussen een knop die je durft in te
    drukken en een die je vermijdt.

    **Commit per document.** Deze functie breekt daarmee de huisregel dat de
    aanroeper de transactie bezit, en dat is hier de juiste keuze. Twee redenen,
    allebei vandaag gemeten:

    - Tien documenten kostten meer dan een kwartier. Eén transactie over zo'n
      run houdt uren een leeslock vast, en een `ALTER TABLE` uit de init-job
      loopt daar met een lock_timeout van 5 seconden op stuk — dat hield op
      2026-09-18 de uitrol tegen.
    - Diezelfde run werd afgekapt, en met één commit aan het eind was ál het
      werk weg. Bij werk dat per stuk minuten kost, hoort elk stuk dat af is
      ook af te zijn.
    """
    ids = list(document_ids)
    bestaand = {
        d for (d,) in session.execute(
            select(DocumentSummary.document_id)
            .where(DocumentSummary.document_id.in_(ids)))
    } if ids else set()
    made = failed = zonder = 0
    for doc_id in ids:
        if doc_id in bestaand:
            continue
        if get_anonymized_text(session, doc_id) is None:
            zonder += 1
            continue
        if for_document(session, generator, doc_id, model) is None:
            failed += 1
        else:
            made += 1
            session.commit()
    return Made(seen=len(ids), made=made, skipped=len(bestaand), failed=failed,
                without_text=zonder)


def by_document(session: Session, document_ids) -> dict[UUID, DocumentSummary]:
    ids = list(document_ids)
    if not ids:
        return {}
    return {
        r.document_id: r for r in session.execute(
            select(DocumentSummary).where(DocumentSummary.document_id.in_(ids))
        ).scalars()
    }
