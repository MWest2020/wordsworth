"""Reversible backfill of an irreversibly-anonymized document (add-reversible-
backfill). DB-backed → runs in CI, skips locally without a DB.

A doc first indexed with the irreversible `DeterministicAnonymizer` (bare `[BSN]`
placeholders, no mapping) is re-processed through the reversible driver: the
stored/index text becomes keyed `[BSN:hash]` tokens, mappings appear, a
`reanonymize` audit event is chained, and the hash-chain still verifies."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from wordsworth import audit
from wordsworth.anonymizer import DeterministicAnonymizer
from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.models import AuditRecord
from wordsworth.pipeline import (
    get_anonymized_text, ingest, process, reanonymize,
)
from wordsworth.pseudonymizer import ReversibleAnonymizer
from wordsworth.states import State

PII_BSN = "123456782"
PII_IBAN = "NL91ABNA0417164300"
PII_EMAIL = "jan.jansen@haarlem.nl"


def _indexed_irreversibly(session, store, index, embedder, pdf):
    doc = ingest(session, store, pdf)
    session.commit()
    st = process(session, doc.id, store, anonymizer=DeterministicAnonymizer(),
                 search_index=index, embedder=embedder)
    session.commit()
    assert st == State.INDEXED
    text = get_anonymized_text(session, doc.id)
    assert "[BSN]" in text and "[BSN:" not in text   # irreversible placeholder
    return doc


def _reversible(session):
    return ReversibleAnonymizer(
        InMemoryKeyProvider(), PostgresMappingStore(session), detect=lambda t: []
    )


def test_reanonymize_backfills_to_reversible(session, mem_store, mem_index,
                                             fake_embedder, born_digital_pii_pdf):
    doc = _indexed_irreversibly(session, mem_store, mem_index, fake_embedder,
                                born_digital_pii_pdf)
    st = reanonymize(session, doc.id, mem_store, anonymizer=_reversible(session),
                     search_index=mem_index, embedder=fake_embedder)
    session.commit()
    assert st == State.INDEXED

    after = get_anonymized_text(session, doc.id)
    assert "[BSN:" in after                                  # keyed, reversible
    for secret in (PII_BSN, PII_IBAN, PII_EMAIL):
        assert secret not in after                           # no clear PII
    # the index entry was upserted to the new text (one entry, same id)
    assert mem_index._docs[str(doc.id)][0] == after
    # a reanonymize access event is chained, with counts only, and verifies
    rec = session.execute(
        select(AuditRecord).where(AuditRecord.step == "reanonymize")
    ).scalar_one()
    assert rec.payload["reanonymized"] is True
    assert PII_BSN not in str(rec.payload)
    ok, bad = audit.verify_chain(session)
    assert ok is True and bad is None


def test_reanonymize_is_idempotent(session, mem_store, mem_index, fake_embedder,
                                   born_digital_pii_pdf):
    doc = _indexed_irreversibly(session, mem_store, mem_index, fake_embedder,
                                born_digital_pii_pdf)
    drv = _reversible(session)
    reanonymize(session, doc.id, mem_store, anonymizer=drv,
                search_index=mem_index, embedder=fake_embedder)
    session.commit()
    first = get_anonymized_text(session, doc.id)
    reanonymize(session, doc.id, mem_store, anonymizer=drv,
                search_index=mem_index, embedder=fake_embedder)
    session.commit()
    assert get_anonymized_text(session, doc.id) == first     # stable pseudonyms
    assert len(mem_index._docs) == 1                         # upsert, one entry


def test_reanonymize_failure_leaves_entry_intact(session, mem_store, mem_index,
                                                 fake_embedder, born_digital_pii_pdf):
    doc = _indexed_irreversibly(session, mem_store, mem_index, fake_embedder,
                                born_digital_pii_pdf)
    before = get_anonymized_text(session, doc.id)
    before_index = mem_index._docs[str(doc.id)]

    class Boom:
        def anonymize(self, text):
            raise RuntimeError("engine down")   # permanent → not retried

    with pytest.raises(RuntimeError):
        reanonymize(session, doc.id, mem_store, anonymizer=Boom(),
                    search_index=mem_index, embedder=fake_embedder)
    session.rollback()
    assert get_anonymized_text(session, doc.id) == before        # text untouched
    assert mem_index._docs[str(doc.id)] == before_index          # index untouched


def test_reanonymize_skips_non_indexed(session, mem_store, mem_index,
                                       fake_embedder, born_digital_pii_pdf):
    doc = ingest(session, mem_store, born_digital_pii_pdf)   # REGISTERED, not indexed
    session.commit()
    st = reanonymize(session, doc.id, mem_store, anonymizer=_reversible(session),
                     search_index=mem_index, embedder=fake_embedder)
    assert st == State.REGISTERED                            # no-op skip
    assert str(doc.id) not in mem_index._docs


def test_a_failing_document_is_named_and_left_in_the_audit(
        session_factory, session, mem_store, mem_index, fake_embedder,
        born_digital_pii_pdf):
    """A backfill that cannot finish a document must say which one, and why.

    On 2026-09-14 a cluster run reported `retryable: 8, failed: 2` and that was
    the whole story: no ids, and no audit record from that day on any of the ten
    documents. The chain said nobody had ever touched them while ten attempts had
    just been made. Counts without identity are not a report, they are a rumour —
    and the only way left to find the ten was to re-run all 770.
    """
    from fastapi.testclient import TestClient

    from wordsworth.api import create_app

    doc = _indexed_irreversibly(session, mem_store, mem_index, fake_embedder,
                                born_digital_pii_pdf)
    before = get_anonymized_text(session, doc.id)

    class Kapot(Exception):
        pass

    def breekt(_session):
        raise Kapot("engine weg")

    app = create_app(session_factory=session_factory, store=mem_store,
                     search_index=mem_index, embedder=fake_embedder,
                     anonymizer_factory=breekt, rate_limiters={})
    uit = TestClient(app).post("/reprocess",
                               json={"document_ids": [str(doc.id)]}).json()

    assert uit["failed"] + uit["retryable"] == 1
    assert uit["problems"] == {str(doc.id): "Kapot"}      # welk document, welke fout
    assert "engine weg" not in str(uit)                   # nooit de boodschap zelf

    session.expire_all()
    stappen = list(session.execute(
        select(AuditRecord.step).where(AuditRecord.document_id == doc.id)
    ).scalars())
    assert "reprocess_failed" in stappen                  # sporen, geen stilte
    assert get_anonymized_text(session, doc.id) == before  # entry ongemoeid
    ok, eerste_fout = audit.verify_chain(session)
    assert ok, f"hash-keten brak bij seq {eerste_fout}"


def test_de_oorzaak_onder_de_wrapper_komt_mee(
        session_factory, session, mem_store, mem_index, fake_embedder,
        born_digital_pii_pdf):
    """De buitenste klasse alleen is niet genoeg.

    Op 2026-09-14 meldden acht documenten alle acht `AnonymizationEngineError`.
    Dat is de bewuste tekstloze wikkel van de driver: hij zegt dát de motor
    weigerde, nooit waarom. De oorzaak eronder — een timeout, een 503, een
    contractbreuk — is het deel waar je iets mee doet, en die viel weg.
    """
    from fastapi.testclient import TestClient

    from wordsworth.api import create_app

    doc = _indexed_irreversibly(session, mem_store, mem_index, fake_embedder,
                                born_digital_pii_pdf)

    class Onderliggend(Exception):
        pass

    class Wikkel(Exception):
        pass

    def breekt(_session):
        try:
            raise Onderliggend("de motor kreeg de tekst 'Jan Jansen, 1234 AB'")
        except Onderliggend as oorzaak:
            raise Wikkel("motor weigerde") from oorzaak

    app = create_app(session_factory=session_factory, store=mem_store,
                     search_index=mem_index, embedder=fake_embedder,
                     anonymizer_factory=breekt, rate_limiters={})
    uit = TestClient(app).post("/reprocess",
                               json={"document_ids": [str(doc.id)]}).json()

    assert uit["problems"] == {str(doc.id): "Wikkel <- Onderliggend"}
    assert "Jan Jansen" not in str(uit)                   # klassen, geen tekst
    assert "1234 AB" not in str(uit)


def test_de_code_van_de_invariant_komt_mee_in_problems(
        session_factory, session, mem_store, mem_index, fake_embedder,
        born_digital_pii_pdf):
    """`AnonymizationInvariantError[waarde-overleefde-vervanging]` — welke
    invariant brak, zonder ook maar een teken uit het document."""
    from fastapi.testclient import TestClient

    from wordsworth.api import create_app
    from wordsworth.openanonymiser_driver import AnonymizationInvariantError

    doc = _indexed_irreversibly(session, mem_store, mem_index, fake_embedder,
                                born_digital_pii_pdf)

    def breekt(_session):
        raise AnonymizationInvariantError(
            "een waarde 'Jan Jansen' overleefde", code="waarde-overleefde-vervanging")

    app = create_app(session_factory=session_factory, store=mem_store,
                     search_index=mem_index, embedder=fake_embedder,
                     anonymizer_factory=breekt, rate_limiters={})
    uit = TestClient(app).post("/reprocess",
                               json={"document_ids": [str(doc.id)]}).json()

    assert uit["problems"] == {
        str(doc.id): "AnonymizationInvariantError[waarde-overleefde-vervanging]"}
    assert uit["failed"] == 1 and uit["retryable"] == 0   # niet tijdelijk
    assert "Jan Jansen" not in str(uit)


def test_de_kenmerken_van_de_invariant_komen_in_de_audit(
        session_factory, session, mem_store, mem_index, fake_embedder,
        born_digital_pii_pdf):
    """Zonder kenmerken stond deze controle acht documenten tegen te houden en
    was van buitenaf niet te achterhalen wát er overleefde — twee
    nabouwpogingen reproduceerden hem niet."""
    from fastapi.testclient import TestClient

    from wordsworth.api import create_app
    from wordsworth.models import AuditRecord
    from wordsworth.openanonymiser_driver import AnonymizationInvariantError

    doc = _indexed_irreversibly(session, mem_store, mem_index, fake_embedder,
                                born_digital_pii_pdf)

    def breekt(_session):
        raise AnonymizationInvariantError(
            "Jan Jansen overleefde", code="waarde-overleefde-vervanging",
            kenmerken={"label": "PERSON", "lengte": 10, "in_bron": 2,
                       "na_vervanging": 1, "woorden": 2, "alnum": False})

    app = create_app(session_factory=session_factory, store=mem_store,
                     search_index=mem_index, embedder=fake_embedder,
                     anonymizer_factory=breekt, rate_limiters={})
    TestClient(app).post("/reprocess", json={"document_ids": [str(doc.id)]})

    session.expire_all()
    rec = session.execute(
        select(AuditRecord).where(AuditRecord.document_id == doc.id,
                                  AuditRecord.step == "reprocess_failed")
    ).scalars().one()
    assert rec.payload["kenmerken"]["label"] == "PERSON"
    assert rec.payload["kenmerken"]["lengte"] == 10
    assert "Jan Jansen" not in str(rec.payload)          # nooit de waarde zelf
