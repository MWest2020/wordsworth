# SPDX-License-Identifier: MIT
"""Onderwerpen: groepen documenten binnen één dossier (onderwerpen).

Na het verwerken van een dossier wil je zien wélke onderwerpen erin zitten. Een
onderwerp is een groep documenten, met een naam uit de termen die die groep
onderscheiden van de rest van hetzelfde dossier.

**Een onderwerp versmalt het zoeken en raakt de score niet.** Dat is de les uit
`zeef` in één zin: clustering is geen ranking. Dat twee documenten in hetzelfde
cluster zitten zegt dat ze op elkaar lijken, niet dat ze allebei antwoord geven
op de vraag die iemand stelt. Het filter staat daarom naast de zoekvraag en
nooit erin — zie `_filters` in `opensearch_index.py`.

Berekend op verzoek en niet bij ingest: één document laat geen onderwerpen zien,
en het hele dossier herberekenen bij elk binnengekomen document is werk dat
kwadratisch groeit voor een antwoord dat op dat moment niemand leest. Wat er
staat, staat er dus mét het moment en het aantal documenten waarover gerekend
is.

Het lidmaatschap woont in de zoekindex en de beschrijving in de database. Eén
bron per vraag.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from zeef.similarity import tokenize

from .models import Topic
from .pseudonymizer import without_tokens
from .search_index import IndexedDocument, SearchIndex

#: Hoe ver twee groepen uit elkaar mogen liggen voordat ze aparte onderwerpen
#: zijn, in cosinusafstand (0 = gelijk, 1 = orthogonaal). Geen natuurwet: een
#: keuze, en daarom een parameter die in het antwoord terugkomt.
DEFAULT_DISTANCE = 0.45

#: Een groep kleiner dan dit is geen onderwerp maar een toevalligheid. De leden
#: houden geen onderwerp; ze blijven gewoon in het dossier te vinden.
DEFAULT_MIN_SIZE = 3

#: Hoeveel termen een berekende naam mag hebben.
_NAME_TERMS = 3

#: Woorden die overal in Nederlandse overheidsstukken staan en dus niets
#: onderscheiden. Bewust kort: de TF-IDF-weging doet het meeste werk, en een
#: lange handgeschreven lijst is een plek waar iemands aanname blijft hangen.
_STOP = {
    "de", "het", "een", "en", "van", "in", "op", "te", "dat", "die", "voor",
    "met", "is", "aan", "als", "er", "bij", "of", "om", "niet", "naar", "zijn",
    "dit", "deze", "wordt", "worden", "kan", "door", "ook", "uit", "over",
    "maar", "heeft", "was", "we", "u", "ik", "hij", "zij", "u", "per", "tot",
    "geen", "nog", "wel", "dan", "meer", "al", "je", "haar", "hun", "ze",
}

#: Puur cijferwerk zegt niets als naam, en een losse hex-staart is precies wat
#: er van een token overblijft als iemand hem tokeniseert in plaats van
#: weghaalt.
_ONLY_DIGITS = re.compile(r"^\d+$")
_HEXISH = re.compile(r"^[0-9a-f]{6,}$")


class TopicError(ValueError):
    """Een berekening die niet kan."""


@dataclass(frozen=True)
class Computed:
    """Het resultaat van één berekening, zoals de aanroeper het te zien krijgt."""

    topics: list[Topic]
    #: Hoeveel documenten er in de index zaten, hoeveel er een vector hadden, en
    #: hoeveel er in geen enkele groep terechtkwamen. Zonder deze drie is een
    #: onderwerpenlijst een bewering zonder noemer.
    seen: int
    with_vector: int
    without_topic: int
    #: Waaraan je kijkt: de afkapafstand en de ondergrens die deze indeling
    #: maakten. Geen natuurwetten maar keuzes, en een indeling zonder die twee
    #: is niet na te rekenen.
    distance: float = DEFAULT_DISTANCE
    min_size: int = DEFAULT_MIN_SIZE


def usable_name(term: str) -> bool:
    """Mag deze term in een onderwerpnaam staan?

    Tokens zijn er dan al uit (`without_tokens`, vóór het tokeniseren). Dit
    vangt wat er ná het tokeniseren nog overblijft dat niets benoemt: stopwoorden,
    kale getallen, en hex-staarten — dat laatste is hoe een token eruitziet als
    iemand hem per ongeluk stukknipt in plaats van weghaalt.
    """
    return (len(term) > 2 and term not in _STOP
            and not _ONLY_DIGITS.match(term) and not _HEXISH.match(term))


def terms_of(text: str) -> list[str]:
    """De termen van een document, zónder pseudonym-tokens.

    De tokens gaan eruit vóór het tokeniseren, niet erna: `[PERSOON:3fa9c2d1]`
    valt anders uiteen in "persoon" en "3fa9c2d1", en dan staat de helft van een
    token alsnog in een naam die op een scherm en in een URL belandt.
    """
    return [t for t in tokenize(without_tokens(text)) if usable_name(t)]


def name_for(members: list[list[str]], document_frequency: Counter,
             total: int) -> str:
    """Een naam uit de termen die deze groep onderscheiden van de rest.

    TF-IDF over het dossier: vaak in deze groep, zeldzaam daarbuiten. Dezelfde
    vorm die `zeef` onder `--no-llm` gebruikt, en om dezelfde reden — een door
    een taalmodel bedachte titel is een bewering waarvan niemand de herkomst kan
    navertellen, en dit systeem verwerkt persoonsgegevens.
    """
    in_group: Counter = Counter()
    for terms in members:
        in_group.update(set(terms))
    scored = [
        (count * math.log(total / (1 + document_frequency[term])), term)
        for term, count in in_group.items()
    ]
    scored.sort(key=lambda p: (-p[0], p[1]))
    best = [term for _score, term in scored[:_NAME_TERMS]]
    return " · ".join(best) if best else "zonder onderscheidende termen"


def _clusters(vectors: list[list[float]], distance: float) -> list[int]:
    """Agglomeratieve clustering (average linkage, cosinusafstand).

    scipy en niet zelfgeschreven: UPGMA met de hand is precies het soort code
    waar een stille fout in gaat zitten die niemand ooit meet. Eén groep is een
    geldig antwoord, en scipy kan niet clusteren op minder dan twee punten —
    vandaar de twee uitzonderingen hierboven.
    """
    if not vectors:
        return []
    if len(vectors) == 1:
        return [1]
    from scipy.cluster.hierarchy import fcluster, linkage
    from scipy.spatial.distance import pdist

    condensed = pdist(vectors, metric="cosine")
    return list(fcluster(linkage(condensed, method="average"),
                         t=distance, criterion="distance"))


def compute(session: Session, index: SearchIndex, dossier_id: UUID, *,
            distance: float = DEFAULT_DISTANCE,
            min_size: int = DEFAULT_MIN_SIZE) -> Computed:
    """Herbereken de onderwerpen van één dossier, en zet ze op de documenten.

    Vervangt wat er was: onderwerpen zijn een momentopname van een dossier, en
    twee generaties naast elkaar laten staan levert een lijst op waarvan niemand
    weet welke helft nog klopt.
    """
    key = str(dossier_id)
    docs = index.documents_in(key)
    with_vector = [d for d in docs if d.vector]

    labels = _clusters([d.vector for d in with_vector], distance)
    grouped: dict[int, list[IndexedDocument]] = {}
    for label, doc in zip(labels, with_vector):
        grouped.setdefault(label, []).append(doc)
    groups = [members for members in grouped.values() if len(members) >= min_size]

    # De noemer voor TF-IDF is het dossier zelf: onderscheidend betekent hier
    # "vaker dan de buren", niet "zeldzaam in het Nederlands".
    terms_by_doc = {d.document_id: terms_of(d.text) for d in docs}
    document_frequency: Counter = Counter()
    for terms in terms_by_doc.values():
        document_frequency.update(set(terms))
    total = max(len(docs), 1)

    old = [t for (t,) in session.execute(
        select(Topic.id).where(Topic.dossier_id == dossier_id))]
    session.execute(delete(Topic).where(Topic.dossier_id == dossier_id))

    now = datetime.now(timezone.utc)
    made: list[Topic] = []
    assigned: dict[str, str] = {}
    for members in sorted(groups, key=len, reverse=True):
        topic = Topic(
            dossier_id=dossier_id,
            computed_name=name_for([terms_by_doc[m.document_id] for m in members],
                                   document_frequency, total),
            computed_at=now,
            document_count=len(members),
        )
        session.add(topic)
        session.flush()
        made.append(topic)
        for member in members:
            assigned[member.document_id] = str(topic.id)

    _write_membership(index, docs, assigned, {str(o) for o in old})
    return Computed(topics=made, seen=len(docs), with_vector=len(with_vector),
                    without_topic=len(docs) - len(assigned),
                    distance=distance, min_size=min_size)


def _write_membership(index: SearchIndex, docs: list[IndexedDocument],
                      assigned: dict[str, str], retired: set[str]) -> None:
    """Zet het nieuwe onderwerp op elk document en haal de oude van dit dossier
    eraf.

    Alleen de onderwerpen van dít dossier gaan eraf. Een document kan in twee
    dossiers zitten en dus in twee onderwerpen; het tweede dossier herberekenen
    mag het eerste niet wissen.
    """
    for doc in docs:
        keep = [t for t in doc.topics if t not in retired]
        new = assigned.get(doc.document_id)
        if new is not None:
            keep.append(new)
        if set(keep) != set(doc.topics):
            index.set_topics(doc.document_id, sorted(set(keep)))


def listing(session: Session, dossier_id: UUID) -> list[Topic]:
    """De onderwerpen van een dossier, grootste eerst."""
    return list(session.execute(
        select(Topic).where(Topic.dossier_id == dossier_id)
        .order_by(Topic.document_count.desc(), Topic.computed_name)
    ).scalars())


def rename(session: Session, topic_id: UUID, name: str) -> Topic:
    """Geef een onderwerp een naam van een mens.

    De berekende naam blijft staan: waar een groep vandaan komt, blijft
    navertelbaar. Een lege naam haalt de gegeven naam weer weg.
    """
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise TopicError("unknown topic")
    topic.given_name = (name or "").strip() or None
    session.flush()
    return topic


def display_name(topic: Topic) -> str:
    """Wat een mens te zien krijgt: zijn eigen naam als die er is."""
    return topic.given_name or topic.computed_name
