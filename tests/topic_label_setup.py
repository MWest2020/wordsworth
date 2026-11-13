# SPDX-License-Identifier: MIT
"""Een dossier met onderwerpen, leden in de index en samenvattingen, voor de
tests van topic-labels-llm. Geen spaCy en geen clustering: de onderwerpen
worden hier neergezet zoals `topics.compute` ze achterlaat (een rij in
`topics`, het id op elk lid in de index), want het labelen is wat getoetst
wordt, niet het groeperen."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone

from wordsworth.dossiers import add, ensure
from wordsworth.generator import GenerationError
from wordsworth.models import DocumentSummary, DocumentText, Topic
from wordsworth.pipeline import register

GOED = {"label": "Kap van bomen in het centrum",
        "description": "Aanvragen en besluiten over het kappen van bomen."}


def dossier(session, index, naam: str = "zaak-labels", topics=None):
    """Zet een dossier neer. `topics` is een lijst van (termen, leden) met per
    lid (vector, samenvatting of None). Geeft (dossier, [Topic], {topic: [doc
    ids in volgorde]})."""
    topics = topics or [("kap · boom · vergunning",
                         [([1.0, 0.0], "Een kapvergunning voor een eik.")] * 3)]
    d = ensure(session, naam)
    session.flush()
    gemaakt, leden = [], {}
    for n, (termen, docs) in enumerate(topics):
        t = Topic(dossier_id=d.id, computed_name=termen,
                  computed_at=datetime.now(timezone.utc), document_count=len(docs))
        session.add(t)
        session.flush()
        gemaakt.append(t)
        leden[t.id] = []
        for i, (vector, samenvatting) in enumerate(docs):
            doc = register(session, f"documents/{naam}-{n}-{i}")
            add(session, d.id, doc.id, actor="test")
            tekst = f"document {n}-{i} over {termen}"
            session.merge(DocumentText(document_id=doc.id, anonymized_text=tekst))
            if samenvatting is not None:
                session.add(DocumentSummary(document_id=doc.id, text=samenvatting,
                                            model="test-model"))
            index.index(str(doc.id), tekst, f"documents/{naam}-{n}-{i}",
                        vector=vector, dossiers=[str(d.id)], topics=[str(t.id)])
            leden[t.id].append(str(doc.id))
    session.commit()
    return d, gemaakt, leden


@dataclass
class Model:
    """Een nep-generator: geeft `antwoord` en onthoudt elke prompt."""

    antwoord: dict = field(default_factory=lambda: dict(GOED))
    model: str = "nep-model"
    prompts: list = field(default_factory=list)

    def generate(self, query, sources):          # pragma: no cover
        raise AssertionError("label, niet generate")

    def summarise(self, text):                   # pragma: no cover
        raise AssertionError("label, niet summarise")

    def label(self, prompt: str) -> dict:
        self.prompts.append(prompt)
        return dict(self.antwoord)


@dataclass
class Kapot(Model):
    """Raist bij elke aanroep, of alleen bij aanroep nummer `bij`."""

    bij: int | None = None

    def label(self, prompt: str) -> dict:
        self.prompts.append(prompt)
        if self.bij is None or len(self.prompts) == self.bij:
            raise GenerationError("ollama weg")
        return dict(self.antwoord)


@dataclass
class Wacht(Model):
    """Blokkeert tot `los` gezet is: een model dat twee minuten nadenkt."""

    los: threading.Event = field(default_factory=threading.Event)
    beantwoord: bool = False

    def label(self, prompt: str) -> dict:
        self.prompts.append(prompt)
        assert self.los.wait(10), "de test heeft het model nooit losgelaten"
        self.beantwoord = True
        return dict(self.antwoord)


class Keep:
    """Een sessie die `with` overleeft, zodat een commando de sessie van de
    test gebruikt (zoals in test_samenvatten.py)."""

    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, *a):
        return False
