# SPDX-License-Identifier: MIT
"""Het label van één onderwerp, geschreven nadat de knop al antwoord gaf
(topic-labels-llm).

De knop op de onderwerpenpagina wacht niet op het model (zie
`console_topics.label_page`); dit is wat er daarna gebeurt, in een
achtergrondtaak van dat verzoek. De uitkomst is één JSON-regel op de
pipeline-logger (`structured_log.log_topic_label`): het onderwerp en
`labelled`, `rejected`, `no_summaries` of `failed`. Nooit de tekst van een
label, en van een fout alleen de klasse: wat afgewezen werd kan een token
bevatten, en een databasefout draagt het label als parameter mee.

Geen wachtrij en geen worker. Herstart het proces midden in een aanroep, dan
is het label er niet en kan de knop opnieuw.
"""
from __future__ import annotations

import threading
from uuid import UUID

from .structured_log import log_topic_label
from .topic_labels import LABEL_SLOT, label_topic

__all__ = ["BEZIG", "LABEL_SLOT", "LOOPT_AL", "in_background"]

BEZIG = "Het label wordt geschreven: bezig, ververs over ongeveer 2 minuten."
LOOPT_AL = ("Niets gestart: er loopt al een label-opdracht. Ververs over "
            "ongeveer 2 minuten en probeer het dan opnieuw.")


def in_background(session_factory, search_index, generator, topic_id: UUID,
                  slot: threading.BoundedSemaphore) -> None:
    """Label één onderwerp en geef het slot vrij, wat er ook gebeurt."""
    try:
        with session_factory() as session:
            uitkomst = label_topic(session, search_index, topic_id, generator)
    except Exception as exc:     # GenerationError, SearchUnavailable, TopicError, ...
        log_topic_label(topic_id=topic_id, outcome="failed", error=exc)
        return
    finally:
        slot.release()
    log_topic_label(topic_id=topic_id, outcome=uitkomst)
