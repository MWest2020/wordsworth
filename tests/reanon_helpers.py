# SPDX-License-Identifier: MIT
"""Shared set-up for the reprocess-counts database tests: a document that was
anonymised BEFORE the particle-name rule, and the anonymiser that re-runs it.

`Hendrik` is a gazetteer first name (`data/voornamen.json`), so after the rule
`Hendrik ter Braak` is one PERSON span. Before the rule a detector saw only the
first name (as GLiNER did in the pilot read of the Gooise Meren dossier), or
nothing at all.
"""
from __future__ import annotations

import io
import json

from wordsworth import particle_names
from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.openanonymiser_driver import Entity
from wordsworth.pipeline import document_domain, ingest, process
from wordsworth.pseudonymizer import ReversibleAnonymizer
from wordsworth.states import State

NAAM = "Hendrik ter Braak"
BSN = "123456782"
ZIN = f"Vergadering met {NAAM} over BSN {BSN} in de raadzaal."
VERBODEN = (NAAM, "Hendrik", "Braak", "Vergadering", "raadzaal", BSN, "[PERSON:",
            "[BSN:", "offset", "start", "end\"")


def pdf(line: str = ZIN) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawString(72, 800, line)
    c.showPage()
    c.save()
    return buf.getvalue()


def niets(_text):
    return []


def alleen_voornaam(text):
    i = text.index("Hendrik")
    return [Entity("PERSON", "Hendrik", i, i + len("Hendrik"))]


def anonymised_before_the_rule(session_factory, store, index, embedder, kp,
                               monkeypatch, detect=niets, line: str = ZIN):
    """Ingest and process `line` with the particle rule switched off."""
    with monkeypatch.context() as m:
        m.setattr(particle_names, "detect", lambda text, first_names=None: [])
        with session_factory() as s:
            doc = ingest(s, store, pdf(line))
            s.commit()
            anon = ReversibleAnonymizer(kp, PostgresMappingStore(s), detect=detect,
                                        domain=document_domain(s, doc.id))
            st = process(s, doc.id, store, anonymizer=anon,
                         search_index=index, embedder=embedder)
            s.commit()
            assert st == State.INDEXED
            return doc.id


def with_the_rule(kp):
    """`make_anonymizer` for reprocess: the same keys, the rule switched on."""
    return lambda s, domain: ReversibleAnonymizer(
        kp, PostgresMappingStore(s), detect=niets, domain=domain)


def new_key_provider():
    return InMemoryKeyProvider()


def count_lines(caplog) -> list[dict]:
    """Every `reprocess_counts` line the run logged, parsed."""
    uit = []
    for rec in caplog.records:
        try:
            parsed = json.loads(rec.getMessage())
        except ValueError:
            continue
        if isinstance(parsed, dict) and parsed.get("event") == "reprocess_counts":
            uit.append(parsed)
    return uit
