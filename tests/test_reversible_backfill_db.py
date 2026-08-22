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
