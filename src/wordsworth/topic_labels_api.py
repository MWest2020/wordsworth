# SPDX-License-Identifier: MIT
"""`POST /topics/{topic_id}/label`: label één onderwerp (topic-labels-llm).

Eén onderwerp per aanroep, en geen route voor een heel dossier: één label is
ongeveer twee minuten modeltijd, zeventien zijn er vijfendertig, en dat past
in geen enkel verzoek. Een dossier labelen is het commando
`python -m wordsworth.onderwerpen_labelen`. Deze route is voor aanroepers in
het cluster; een browser gaat door Cloudflare (100 s) en oauth2-proxy (30 s)
en gebruikt de knop in de console, die niet wacht (`console_topics.py`).

Achter de corpus-leespoort, dezelfde als die van de samenvattingen: een label
wordt uit samenvattingen geschreven. Eén label tegelijk per proces, hetzelfde
slot als de knop: een tweede aanroep krijgt 409. Een onbereikbaar model of een
onbereikbare index is een 503 die zegt welke van de twee; `api.py` heeft
daar geen algemene vertaling voor, dus die staat hier.
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from .generator import GenerationError, Generator
from .models import Topic
from .search_index import SearchIndex, SearchUnavailable
from .concurrency import limiter
from .topic_labels import LABEL_SLOT, LABELLED, TopicRecomputed, label_topic
from .topics import TopicError


class TopicLabelResponse(BaseModel):
    """Wat er na de aanroep staat. `labelled: false` met een `reason`
    (`rejected` of `no_summaries`): het onderwerp houdt wat het had, en dan
    staan hieronder het label en de herkomst van vóór deze aanroep."""

    topic_id: str
    labelled: bool
    reason: str | None = None
    label: str | None = None
    description: str | None = None
    model: str | None = None
    at: datetime | None = None


def mount(app: FastAPI, session_factory, search_index: SearchIndex,
          generator: Generator | None,
          guard: Callable[[Request], None]) -> None:
    """Zet de route op de app zelf: een `include_router` laat in deze
    FastAPI-versie een route zonder `path` achter in `app.routes`."""

    @app.post("/topics/{topic_id}/label", summary="Label één onderwerp",
              tags=["write"])
    def label_one(request: Request, topic_id: UUID) -> TopicLabelResponse:
        """Laat het taalmodel in het cluster dit onderwerp een label en één
        zin uitleg geven. Duurt ongeveer twee minuten."""
        guard(request)
        if generator is None:
            raise HTTPException(status_code=503,
                                detail="language model not configured")
        slot = limiter(LABEL_SLOT, 1)
        if not slot.acquire(blocking=False):
            raise HTTPException(status_code=409,
                                detail="er loopt al een label-opdracht")
        try:
            with session_factory() as session:
                return _label(session, topic_id)
        finally:
            slot.release()

    def _label(session, topic_id: UUID) -> TopicLabelResponse:
        try:
            uitkomst = label_topic(session, search_index, topic_id, generator)
        except TopicRecomputed:
            raise HTTPException(status_code=409,
                                detail="onderwerp is opnieuw berekend")
        except TopicError:
            raise HTTPException(status_code=404, detail="unknown topic")
        except SearchUnavailable:
            raise HTTPException(status_code=503, detail="search index unreachable")
        except GenerationError:
            raise HTTPException(status_code=503,
                                detail="language model unreachable")
        # Opnieuw lezen: het object in de sessie zegt niet of de rij er nog is.
        topic = session.get(Topic, topic_id, populate_existing=True)
        if topic is None:       # verdween na een afwijzing: ook herberekend
            raise HTTPException(status_code=409,
                                detail="onderwerp is opnieuw berekend")
        return TopicLabelResponse(
            topic_id=str(topic_id), labelled=uitkomst == LABELLED,
            reason=None if uitkomst == LABELLED else uitkomst,
            label=topic.llm_label, description=topic.llm_description,
            model=topic.llm_model, at=topic.llm_at)
