# SPDX-License-Identifier: MIT
"""Het corpus opnieuw door de straat halen (reprocess).

Hier en niet in `api.py`, omdat dit meer dan één aanroeper heeft. Op
2026-09-20 bouwde ik deze lus na in een Kubernetes-Job en liet daarbij de
foutregistratie weg -- precies de registratie die er in september was
ingebouwd nadat dezelfde vergissing een run onzichtbaar maakte. De lus die het
spoor schrijft hoort op één plek te staan, en dan schrijft iedereen die hem
gebruikt hetzelfde spoor.

Continue-on-failure: een hapering laat de bestaande invoer van een document
intact en telt als `retryable`; een blijvende fout telt als `failed`. Beide
krijgen een auditregel, want een run die achteraf onzichtbaar is, is geen run
die je kunt nakijken.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from . import audit
from .models import AuditRecord, Document
from .pdf_text import TEXT_SOURCE
from .pipeline import (current_state, document_domain, lists_hash_of,
                       reanonymize, text_source_of)
from .retry import is_transient
from .states import State


def safe_traits(exc: BaseException) -> dict:
    """`kenmerken` van de eerste fout in de keten die ze draagt.

    Alleen wat de raise-site zelf als veilig heeft aangemerkt:
    type, lengte, aantallen. De audit-keten is exporteerbaar, dus
    hier hoort nooit iets uit een document in te staan.
    """
    e, gezien = exc, set()
    while e is not None and id(e) not in gezien:
        gezien.add(id(e))
        k = getattr(e, "kenmerken", None)
        if isinstance(k, dict) and k:
            return {"kenmerken": k}
        e = e.__cause__ or e.__context__
    return {}

def cause_chain(exc: BaseException) -> str:
    """The exception classes from outside in, e.g.
    ``AnonymizationEngineError <- ReadTimeout``.

    The outermost class alone was not enough. On 2026-09-14 eight
    documents all reported `AnonymizationEngineError`, which is the
    driver's deliberate no-text wrapper: it says the engine refused,
    never why. The cause underneath — a timeout, a 503, a contract
    break — is the part you act on, and it was being dropped.

    Class NAMES only. `str(exc)` of an engine error can quote the
    fragment it choked on; a class name cannot.
    """
    namen, e, gezien = [], exc, set()
    while e is not None and id(e) not in gezien and len(namen) < 5:
        gezien.add(id(e))
        naam = type(e).__name__
        # Een vaste code zegt WELKE invariant brak. Alleen een code
        # uit een gesloten woordenlijst — nooit `str(e)`.
        code = getattr(e, "code", None)
        if isinstance(code, str) and code:
            naam = f"{naam}[{code}]"
        namen.append(naam)
        e = e.__cause__ or e.__context__
    return " <- ".join(namen)

def note_failure(session_factory, document_id: UUID, exc: Exception) -> None:
    """Leave a trace in the audit chain that this document was tried
    and did not make it.

    Without this the run is invisible afterwards: the nine documents
    that failed on 2026-09-14 had no audit record from that day at
    all, so the chain said "nobody ever touched these" while ten
    attempts had just been made. A failure that leaves no evidence is
    indistinguishable from a step that never ran.

    Only the exception CLASS is recorded. The message may quote the
    document, and the audit chain is exportable — clear text has no
    business in it. The state does not change: the existing entry is
    intact, which is what continue-on-failure means.
    """
    try:
        with session_factory() as session:
            state = current_state(session, document_id)
            audit.append(session, document_id=document_id,
                         from_state=state.value, to_state=state.value,
                         step="reprocess_failed",
                         payload={"error_class": cause_chain(exc),
                                  "transient": is_transient(exc),
                                  **safe_traits(exc)})
            session.commit()
    except Exception:  # noqa: BLE001 — bookkeeping must never
        pass          # take down the run it is bookkeeping for


def _value_not_located_detail(session, document_id: UUID) -> str | None:
    """The `problems` text for this document, if the run just finished ended
    in `value-not-located` (pdf-redaction-locate) rather than a usable box
    map. Names the PII type and the counts, never the value -- the same
    contract the audit record itself keeps."""
    row = session.execute(
        select(AuditRecord.step, AuditRecord.payload)
        .where(AuditRecord.document_id == document_id)
        .order_by(AuditRecord.seq.desc()).limit(1)
    ).first()
    if row is None or row[0] != "value-not-located":
        return None
    payload = row[1] or {}
    return (f"value-not-located: {payload.get('pii_type')} "
            f"({payload.get('in_positioned')} of {payload.get('in_anonymized')} located)")


def one(session_factory, document_id: UUID, *, make_anonymizer,
        store, search_index=None, embedder=None,
        resolve_key_provider=None) -> tuple[str, str | None]:
    with session_factory() as session:
        state = current_state(session, document_id)
        if state not in (State.INDEXED, State.ANONYMIZED):
            return "skipped", None
        anon = make_anonymizer(session, document_domain(session, document_id))
        # pdf-redaction: a key provider lets reanonymize recompute the box map
        # under the lists this run just reanonymized under; absent in
        # irreversible mode, where there is no mapping to decrypt anyway.
        key_provider = resolve_key_provider(session) if resolve_key_provider else None
        mapping_store = None
        if key_provider is not None:
            from .mapping_store import PostgresMappingStore

            mapping_store = PostgresMappingStore(session)
        reanonymize(session, document_id, store, anonymizer=anon,
                    search_index=search_index, embedder=embedder,
                    key_provider=key_provider, mapping_store=mapping_store)
        session.commit()
        # The text/embed/index work above succeeded regardless -- only the box
        # map may not have (pdf-redaction-locate): report it, do not hide a
        # reanonymized document behind a different counts bucket.
        detail = _value_not_located_detail(session, document_id)
    return "reanonymized", detail

def outdated(session, ids, lists_hash: str | None):
    """De documenten die nog niet onder deze lijst-hash zijn verwerkt, OF nog
    niet onder de ene pdfium-extractie (pdf-redaction-locate).

    Zie `pipeline.lists_hash_of`/`text_source_of`: "al bijgewerkt" is een feit
    uit het spoor en geen tijdstempel die iemand moet onthouden.
    """
    return [i for i in ids if lists_hash_of(session, i) != lists_hash
            or text_source_of(session, i) != TEXT_SOURCE]


def indexed_ids(session) -> list[UUID]:
    """Alles wat geindexeerd is -- de standaardverzameling voor een backfill."""
    return [i for i in session.execute(select(Document.id)).scalars()
            if current_state(session, i) == State.INDEXED]


def run(session_factory, ids, *, make_anonymizer, store, search_index=None,
        embedder=None, on_progress=None, resolve_key_provider=None) -> tuple[dict, dict]:
    """Verwerk `ids` en geef (tellingen, problemen).

    `on_progress(n, totaal)` wordt na elk document aangeroepen, zodat een Job
    voortgang kan tonen zonder dat deze lus iets van printen hoeft te weten.
    """
    counts = {"reanonymized": 0, "skipped": 0, "retryable": 0, "failed": 0}
    problems: dict[str, str] = {}
    for n, document_id in enumerate(ids, 1):
        try:
            outcome, detail = one(session_factory, document_id,
                       make_anonymizer=make_anonymizer, store=store,
                       search_index=search_index, embedder=embedder,
                       resolve_key_provider=resolve_key_provider)
            counts[outcome] += 1
            if detail is not None:
                problems[str(document_id)] = detail
        except Exception as exc:   # never leaks text; entry left intact
            counts["retryable" if is_transient(exc) else "failed"] += 1
            problems[str(document_id)] = cause_chain(exc)
            note_failure(session_factory, document_id, exc)
        if on_progress is not None:
            on_progress(n, len(ids))
    return counts, problems

