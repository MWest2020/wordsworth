# SPDX-License-Identifier: MIT
"""Het label van één onderwerp, geschreven nadat de knop al antwoord gaf
(topic-labels-llm).

De knop op de onderwerpenpagina wacht niet op het model (zie
`console_topics.label_page`); dit is wat er daarna gebeurt, in een
achtergrondtaak van dat verzoek. De uitkomst is één logregel met het
onderwerp en `labelled`, `rejected`, `no_summaries` of `failed`. Nooit de
tekst van een afgewezen label: wat afgewezen werd, kan een token of een
naam bevatten, en een log is geen plek die de reveal-poort bewaakt.

Geen wachtrij en geen worker. Herstart het proces midden in een aanroep, dan
is het label er niet en kan de knop opnieuw.
"""
from __future__ import annotations

import logging
import threading
from uuid import UUID

from .generator import GenerationError
from .search_index import SearchUnavailable
from .topic_labels import label_topic
from .topics import TopicError

log = logging.getLogger(__name__)

#: De naam van het ene slot voor labels in `concurrency.limiter`.
LABEL_SLOT = "topic-label"
BEZIG = "Het label wordt geschreven: bezig, ververs over ongeveer 2 minuten."
LOOPT_AL = ("Niets gestart: er loopt al een label-opdracht. Ververs over "
            "ongeveer 2 minuten en probeer het dan opnieuw.")


def in_background(session_factory, search_index, generator, topic_id: UUID,
                  slot: threading.BoundedSemaphore) -> None:
    """Label één onderwerp en geef het slot vrij, wat er ook gebeurt."""
    try:
        with session_factory() as session:
            try:
                uitkomst = label_topic(session, search_index, topic_id, generator)
            except (GenerationError, SearchUnavailable, TopicError) as exc:
                log.warning("topic label topic=%s outcome=failed reason=%s",
                            topic_id, type(exc).__name__)
                return
            except Exception:
                log.exception("topic label topic=%s outcome=failed", topic_id)
                return
        log.info("topic label topic=%s outcome=%s", topic_id, uitkomst)
    finally:
        slot.release()
