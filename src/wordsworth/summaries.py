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
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from .generator import GenerationError, Generator
from .models import DocumentSummary
from .pipeline import get_anonymized_text
from .pseudonymizer import without_tokens

_SPATIES = re.compile(r"\s+")
#: Wat er van een token overblijft in een samenvatting. Zichtbaar, want de
#: eerste productierun gaf zinnen als "de effecten van de aanzanding op het  en
#: geeft aanbevelingen" -- het gat leest als een taalfout in plaats van als een
#: weglating, en dan gaat de lezer twijfelen aan het model in plaats van te zien
#: dat er iets is weggehaald.
WEGGELATEN = "…"
_OPEENVOLGEND = re.compile(r"(?:…[\s,.;:]*)+…")
#: Een KALE pseudonym-id, zonder de blokhaken eromheen.
#:
#: Gemeten op 2026-09-19: het model schreef "op locatie 9e9d0346, met hulp van
#: organisatie a4e276dd" — het had `[LOCATION:9e9d0346]` geparafraseerd en de
#: haken laten vallen. `without_tokens` zoekt de volledige vorm en liet die
#: staarten dus staan.
#:
#: Dat is niet onschuldig. Die acht tekens ZIJN de sleutel: hij is stabiel over
#: documenten heen, dus hij koppelt "dit stuk en dat stuk gaan over dezelfde
#: persoon" zonder dat er ooit een token wordt onthuld. En wie hem terugzet
#: tussen haken heeft een token dat de reveal wél accepteert.
#:
#: Woordgrenzen eromheen, en minstens één cijfer: anders sneuvelen gewone
#: woorden als "adviseur" of "beoefend" die toevallig uit hex-letters bestaan.
_KALE_ID = re.compile(r"(?<![0-9a-zA-Z])(?=[0-9a-f]{8}(?![0-9a-zA-Z]))"
                      r"(?=[0-9a-f]*\d)[0-9a-f]{8}")


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


#: De "maker" van een extractieve samenvatting. Staat in hetzelfde veld als de
#: modelnaam, want dat veld beantwoordt één vraag: wat heeft deze tekst
#: gemaakt. Het scherm leest hem om te weten of het een citaat toont of een
#: bewering, en dat onderscheid is de hele reden dat dit veld er is.
EXTRACTIEF = "extractief"

#: Hoeveel tekens een extractieve samenvatting hoogstens meeneemt.
_EXTRACT_TEKENS = 300

#: Een regel die alleen uit weglatingstekens, leestekens, cijfers of losse
#: letters bestaat, benoemt niets. In gescande brieven staan die bovenaan bij
#: bosjes: paginanummers, kenmerkstreepjes, de resten van een briefhoofd.
_ZEGT_NIETS = re.compile(r"^[\W\d_…]*$")


def is_citation(model: str) -> bool:
    """Is deze samenvatting een citaat (extractief) of een bewering (model)?"""
    return model == EXTRACTIEF


def extractive(text: str) -> str:
    """De eerste regels die iets zeggen, letterlijk overgenomen.

    Nul modelaanroepen, en daarmee nul seconden — tegenover 123 seconden per
    document voor het model op deze hardware (één core, geen GPU).

    Maar de reden is niet alleen de tijd. Dit is een **citaat**: je kunt het
    terugvinden in de opgeslagen tekst. Een modelsamenvatting is een bewering.
    Bij bestuurlijke post staat bovendien juist in de eerste regels wat je wilt
    weten — afzender, datum, kenmerk, onderwerp — en dat is precies wat een
    taalmodel van 3b op OCR-ruis het slechtst navertelt.

    De tokens gaan er net zo goed uit als bij een modelsamenvatting: ze horen
    niet in een veld dat op een scherm belandt.
    """
    regels = []
    lengte = 0
    for regel in (text or "").splitlines():
        kaal = clean(regel)
        if not kaal or _ZEGT_NIETS.match(kaal):
            continue
        regels.append(kaal)
        lengte += len(kaal)
        if lengte >= _EXTRACT_TEKENS:
            break
    uit = " ".join(regels)[:_EXTRACT_TEKENS].strip()
    return uit + "…" if len(" ".join(regels)) > _EXTRACT_TEKENS else uit


def clean(generated: str) -> str:
    """De tekst zoals hij opgeslagen wordt: zonder tokens, zonder dubbele witruimte.

    Leeg terug betekent: dit is geen samenvatting. De aanroeper slaat dan niets
    op — een placeholder die eruitziet als inhoud is erger dan een leeg veld,
    want hij wordt gelezen als de samenvatting van een document dat niemand
    heeft samengevat.
    """
    tekst = _SPATIES.sub(" ", without_tokens(generated or "", WEGGELATEN))
    # En de losse staarten: een model dat een token parafraseert laat de haken
    # vallen en houdt de id over.
    tekst = _KALE_ID.sub(WEGGELATEN, tekst)
    # Twee weglatingen naast elkaar zijn één weglating voor de lezer.
    tekst = _OPEENVOLGEND.sub(WEGGELATEN, tekst)
    tekst = _SPATIES.sub(" ", tekst).strip()
    # Alleen nog weglatingstekens en leestekens: dan is er niets samengevat.
    return "" if not tekst.strip("… ,.;:-") else tekst


def for_document(session: Session, generator: Generator | None, document_id: UUID,
                 model: str) -> DocumentSummary | None:
    """Maak en bewaar één samenvatting, of geef None als dat niet lukt.

    `generator=None` betekent: extractief, de eerste regels die iets zeggen.
    Geen vlag erbij, want er ís geen derde geval — zonder model kan er geen
    modelsamenvatting zijn.
    """
    tekst = get_anonymized_text(session, document_id)
    if not tekst:
        return None
    if generator is None:
        samenvatting, model = extractive(tekst), EXTRACTIEF
        if not samenvatting:
            return None
        return _bewaar(session, document_id, samenvatting, model)
    try:
        rauw = generator.summarise(tekst)
    except GenerationError:
        # Een mislukte generatie is geen samenvatting. Geen halve tekst, geen
        # foutmelding die als inhoud op een scherm belandt.
        return None
    samenvatting = clean(rauw)
    if not samenvatting:
        return None
    return _bewaar(session, document_id, samenvatting, model)


def _bewaar(session: Session, document_id: UUID, tekst: str,
            model: str) -> DocumentSummary:
    """Schrijf de samenvatting weg, ook als een ander hem net schreef.

    Een upsert en geen lezen-dan-schrijven. `compute()` kijkt aan het begin één
    keer welke documenten al een samenvatting hebben, en tussen dat moment en de
    insert kan er minuten zitten — bij een taalmodel zelfs kwartieren. Op
    2026-09-19 gebeurde dat: een handmatige run en een Job liepen elkaar in de
    weg en de Job viel om op een `duplicate key`, nadat hij al dertien minuten
    had gewerkt.

    Wie het laatst schrijft wint, en dat is hier goed: het is dezelfde
    samenvatting over dezelfde tekst, hoogstens door een ander model. Het model
    en het moment gaan mee, dus wat er staat blijft navertelbaar.
    """
    from sqlalchemy.dialects.postgresql import insert

    now = datetime.now(timezone.utc)
    stmt = insert(DocumentSummary).values(
        document_id=document_id, text=tekst, model=model, created_at=now)
    session.execute(stmt.on_conflict_do_update(
        index_elements=[DocumentSummary.document_id],
        set_={"text": tekst, "model": model, "created_at": now}))
    session.flush()
    return session.get(DocumentSummary, document_id)


def compute(session: Session, generator: Generator | None, document_ids,
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
