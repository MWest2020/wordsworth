# SPDX-License-Identifier: MIT
"""Een leesbaar label voor een onderwerp, geschreven door het taalmodel in het
cluster (topic-labels-llm).

De TF-IDF-naam (`onderdeel · verder · krijgen`) zegt welke woorden vaak zijn,
niet waar een groep over gaat. Het model krijgt per onderwerp de samenvattingen
van de hoogstens acht documenten die het dichtst bij het midden van de groep
liggen, plus de termen, en schrijft een label en één zin uitleg.

Wat erin gaat is gepseudonimiseerd (opgeslagen samenvattingen en termen); wat
eruit komt is een bewering van een model, en wordt dus opgeslagen met model en
moment, net als een samenvatting. Een antwoord dat niet deugt wordt
afgewezen, niet gerepareerd: het onderwerp houdt wat het had.

Wie in een onderwerp zit, en met welke vector, staat alleen in de zoekindex.
Een `SearchUnavailable` bij die leesactie wordt hier niet gevangen: dan wordt
er niets gelabeld en zegt de aanroeper dat.

Beide functies committen, en breken daarmee de huisregel dat de aanroeper de
transactie bezit, om dezelfde reden als `summaries.compute`: een modelaanroep
duurt hier twee minuten, en een leestransactie die zo lang openstaat houdt een
`ALTER TABLE` uit de init-job tegen. Er staat dus geen transactie open terwijl
het model schrijft, en elk label dat af is, is af.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import ObjectDeletedError, StaleDataError

from .generator import GenerationError, Generator
from .models import Topic
from .search_index import IndexedDocument, SearchIndex
from .summaries import by_document
from .topic_label_check import DESCRIPTION_CHARS, LABEL_WORDS, validate
from .topics import TopicError, listing

#: Hoeveel van de centraalste documenten het model te zien krijgt.
CENTRAL = 8
#: Eén label tegelijk, per proces (`concurrency.limiter`): de knop en de
#: route delen dit slot. Over pods of workers heen telt het niet.
LABEL_SLOT = "topic-label"

LABELLED, REJECTED, NO_SUMMARIES = "labelled", "rejected", "no_summaries"


class TopicRecomputed(TopicError):
    """Het onderwerp verdween terwijl het model schreef: het dossier is in
    die twee minuten opnieuw berekend. Het label hoort bij een groep die niet
    meer bestaat en wordt dus niet opgeslagen."""

@dataclass
class Labelled:
    """De telling van één run over een dossier."""

    seen: int = 0
    labelled: int = 0
    rejected: int = 0
    no_summaries: int = 0
    skipped: int = 0
    failed: int = 0


def central(docs: list[IndexedDocument], topic_id: str,
            n: int = CENTRAL) -> list[str]:
    """De ids van de hoogstens `n` leden die het dichtst bij het zwaartepunt
    van hun vectoren liggen. Een lid zonder vector heeft geen plek en telt
    niet mee; bij gelijke afstand beslist de id, zodat het herhaalbaar is."""
    members = [d for d in docs if topic_id in d.topics and d.vector]
    if not members:
        return []
    dim = len(members[0].vector)
    centroid = [sum(d.vector[i] for d in members) / len(members)
                for i in range(dim)]

    def afstand(d: IndexedDocument) -> float:
        return sum((x - c) ** 2 for x, c in zip(d.vector, centroid))

    return [d.document_id for d in sorted(
        members, key=lambda d: (afstand(d), d.document_id))[:n]]


def prompt(terms: list[str], summaries: list[str]) -> str:
    blocks = "\n".join(f"- {s}" for s in summaries)
    return (
        "Hieronder staan de samenvattingen van de meest centrale documenten van "
        "één onderwerp in een dossier, en de termen die dat onderwerp "
        "onderscheiden van de rest. Geef het onderwerp in het Nederlands een "
        f"label van hoogstens {LABEL_WORDS} woorden en een beschrijving van één "
        f"zin van hoogstens {DESCRIPTION_CHARS} tekens. Schrijf alleen wat de "
        "samenvattingen dragen; verzin niets. Neem GEEN codes tussen blokhaken "
        "over (zoals [PERSOON:3fa9c2d1]), schrijf geen plaatshouders zoals "
        "[NAAM] en noem geen webadressen. Antwoord met JSON: "
        '{"label": "<label>", "description": "<beschrijving>"}.\n\n'
        f"TERMEN: {', '.join(terms)}\n\nSAMENVATTINGEN:\n{blocks}"
    )


def _label(session: Session, topic: Topic, docs: list[IndexedDocument],
           generator: Generator) -> str:
    model = generator.model     # wie het label schreef; vóór het werk, niet erna
    ids = central(docs, str(topic.id))
    found = by_document(session, [UUID(i) for i in ids])
    summaries = [found[UUID(i)].text for i in ids if UUID(i) in found]
    if not summaries:
        return NO_SUMMARIES
    vraag = prompt(topic.computed_name.split(" · "), summaries)
    session.commit()            # geen open transactie tijdens de modelaanroep
    checked = validate(generator.label(vraag))   # GenerationError: naar boven
    if checked is None:
        return REJECTED
    try:
        topic.llm_label, topic.llm_description = checked
        topic.llm_model = model
        topic.llm_at = datetime.now(timezone.utc)
        session.commit()
    except (StaleDataError, ObjectDeletedError) as exc:
        session.rollback()
        raise TopicRecomputed("topic recomputed while labelling") from exc
    return LABELLED


def label_topic(session: Session, index: SearchIndex, topic_id: UUID,
                generator: Generator) -> str:
    """Label één onderwerp. Geeft `labelled`, `rejected` of `no_summaries`;
    `TopicError` voor een onbekend onderwerp, `TopicRecomputed` als het
    tijdens de aanroep verdween, en `GenerationError` en
    `SearchUnavailable` gaan ongewijzigd naar de aanroeper."""
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise TopicError("unknown topic")
    docs = index.documents_in(str(topic.dossier_id))
    return _label(session, topic, docs, generator)


def label_topics(session: Session, index: SearchIndex, dossier_id: UUID,
                 generator: Generator, *, again: bool = False) -> Labelled:
    """Label elk onderwerp van een dossier dat nog geen label heeft (`again`:
    allemaal). Een mislukte modelaanroep kost dat ene onderwerp, niet de run;
    het telt als `failed` en het onderwerp houdt zijn naam. Een onderwerp dat
    tijdens de aanroep verdween (herberekend) telt ook als `failed`."""
    docs = index.documents_in(str(dossier_id))    # SearchUnavailable: naar boven
    counts = Labelled()
    for topic in listing(session, dossier_id):
        counts.seen += 1
        if topic.llm_label and not again:
            counts.skipped += 1
            continue
        try:
            outcome = _label(session, topic, docs, generator)
        except (GenerationError, TopicRecomputed):
            session.rollback()
            counts.failed += 1
            continue
        setattr(counts, outcome, getattr(counts, outcome) + 1)
    return counts
