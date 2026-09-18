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

#: Een onderwerp dat meer dan dit deel van het dossier is, zegt niets. "Waar
#: gaat dit dossier over" beantwoorden met "hier gaat het over" is geen antwoord.
#:
#: Dit vervangt een vaste afkapafstand. Die stond op 0.45 en gaf op het eerste
#: echte corpus (Gooise Meren, 567 documenten) één groep van 443 — 78% van het
#: dossier. Gemeten over hetzelfde corpus:
#:
#:     afstand 0.45 -> grootste groep 78%
#:     afstand 0.30 -> grootste groep 62%
#:     afstand 0.20 -> grootste groep 50%
#:     afstand 0.15 -> grootste groep 24%
#:
#: Een vast getal is dus geen eigenschap van de wereld maar van dít corpus, en
#: op het volgende corpus is het weer mis. De eigenschap die je wél wilt is
#: direct op te schrijven: geen enkel onderwerp mag het dossier zijn.
DEFAULT_MAX_SHARE = 0.25

#: Een groep kleiner dan dit is geen onderwerp maar een toevalligheid. De leden
#: houden geen onderwerp; ze blijven gewoon in het dossier te vinden.
DEFAULT_MIN_SIZE = 3

#: Hoeveel termen een berekende naam mag hebben.
_NAME_TERMS = 3

#: Welk deel van een groep een term minstens moet dekken voordat hij de groep
#: mag benoemen. Zie `name_for`: hieronder zit de OCR-ruis.
_MIN_GROUP_SHARE = 0.30

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
    distance: float = 0.0
    min_size: int = DEFAULT_MIN_SIZE
    max_share: float = DEFAULT_MAX_SHARE


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

    **Een term moet de groep vertegenwoordigen, niet één document erin.** Zonder
    die eis kiest TF-IDF met voorliefde OCR-ruis: een scanfout als
    "aannemersbedtif" staat in precies één document en nergens anders in het
    dossier, en scoort daarmee maximaal onderscheidend. Het eerste echte corpus
    gaf namen als "argument · athandeling · bouwregels" en "2anleg ·
    aannemersbedrif · aannemersbedtif" — drie spellingen van hetzelfde woord,
    geen van alle een onderwerp.

    Dus: minstens twee documenten van de groep, en minstens `_MIN_GROUP_SHARE`
    ervan. Een typefout haalt die drempel niet; een onderwerp wel.
    """
    in_group: Counter = Counter()
    for terms in members:
        in_group.update(set(terms))
    drempel = max(2, math.ceil(_MIN_GROUP_SHARE * len(members)))
    scored = [
        (count * math.log(total / (1 + document_frequency[term])), term)
        for term, count in in_group.items()
        if count >= drempel
    ]
    scored.sort(key=lambda p: (-p[0], p[1]))
    best = [term for _score, term in scored[:_NAME_TERMS]]
    return " · ".join(best) if best else "zonder onderscheidende termen"


def _clusters(vectors: list[list[float]], max_share: float = DEFAULT_MAX_SHARE
              ) -> tuple[list[int], float]:
    """Agglomeratieve clustering (average linkage, cosinusafstand).

    Geeft de indeling én de afstand waarop geknipt is. Dat tweede hoort erbij:
    zonder is de indeling niet na te rekenen.

    De boom wordt één keer gebouwd en daarna doorgesneden op de hoogtes die de
    boom zélf heeft — de afstanden waarop groepen samenvloeien. Gezocht wordt de
    hóógste snede waarbij geen groep nog groter is dan `max_share` van het
    geheel: hoe hoger, hoe grover, en grof is goed zolang geen onderwerp het
    dossier wordt.

    Geen lijstje vaste afstanden om te proberen. Dat lijstje zou zelf weer een
    aanname over corpusdichtheid zijn, en precies daaraan ging de vaste 0.45 ten
    onder.

    Groepsgrootte loopt mee met de hoogte, dus dit is een binaire zoektocht en
    geen 566 pogingen. Onder de laagste hoogte is elk document zijn eigen groep
    — er is dus altijd een antwoord, ook al is dat "geen enkel onderwerp", en
    dat is voor een dossier van identieke documenten het eerlijke antwoord.

    scipy en niet zelfgeschreven: UPGMA met de hand is precies het soort code
    waar een stille fout in gaat zitten die niemand ooit meet.
    """
    if not vectors:
        return [], 0.0
    if len(vectors) == 1:
        return [1], 0.0
    from collections import Counter as _Counter

    from scipy.cluster.hierarchy import fcluster, linkage
    from scipy.spatial.distance import pdist

    boom = linkage(pdist(vectors, metric="cosine"), method="average")
    hoogtes = sorted({0.0, *(float(h) for h in boom[:, 2])})
    grens = max_share * len(vectors)

    def indeling(hoogte: float) -> list[int]:
        return list(fcluster(boom, t=hoogte, criterion="distance"))

    def past(hoogte: float) -> bool:
        return max(_Counter(indeling(hoogte)).values()) <= grens

    laag, hoog = 0, len(hoogtes) - 1
    beste = 0
    while laag <= hoog:
        midden = (laag + hoog) // 2
        if past(hoogtes[midden]):
            beste = midden
            laag = midden + 1
        else:
            hoog = midden - 1
    # Niet afronden: op een dicht corpus liggen de hoogtes rond 1e-4, en dan
    # maakt afronden op vier decimalen er 0.0 van — een getal dat zegt dat er
    # niet geknipt is terwijl dat wel gebeurd is. Afronden is voor het scherm.
    return indeling(hoogtes[beste]), hoogtes[beste]


def compute(session: Session, index: SearchIndex, dossier_id: UUID, *,
            max_share: float = DEFAULT_MAX_SHARE,
            min_size: int = DEFAULT_MIN_SIZE) -> Computed:
    """Herbereken de onderwerpen van één dossier, en zet ze op de documenten.

    Vervangt wat er was: onderwerpen zijn een momentopname van een dossier, en
    twee generaties naast elkaar laten staan levert een lijst op waarvan niemand
    weet welke helft nog klopt.
    """
    # Eerst de mapping. Het `topics`-veld is nieuw, en in productie wordt
    # `ensure_ready` alleen bij ingest aangeroepen -- dus zonder dit schrijft de
    # eerste `set_topics` een veld dat OpenSearch dynamisch mapt, en een lijst
    # strings wordt dan `text` met een `.keyword`-subveld in plaats van
    # `keyword`. Een `term`-filter op het ruwe veld matcht daarna niets, zonder
    # fout: de zoekopdracht zegt gewoon "niets gevonden". Precies wat er op
    # 2026-09-18 met `dossiers` gebeurde.
    index.ensure_ready()
    key = str(dossier_id)
    docs = index.documents_in(key)
    with_vector = [d for d in docs if d.vector]

    labels, distance = _clusters([d.vector for d in with_vector], max_share)
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
                    distance=distance, min_size=min_size, max_share=max_share)


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
