import re

from sqlalchemy import select

from wordsworth import audit
from wordsworth.anonymizer import Anonymizer
from wordsworth.keys import StubKeyProvider
from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.models import AuditRecord
from wordsworth.pipeline import get_anonymized_text, ingest, process, register
from wordsworth.pseudonymizer import Pseudonymizer, deanonymize
from wordsworth.states import State

PII_BSN = "123456782"
PII_IBAN = "NL91ABNA0417164300"
PII_EMAIL = "jan.jansen@haarlem.nl"


def _pseudo(session):
    return Pseudonymizer(StubKeyProvider("pass"), PostgresMappingStore(session))


def test_satisfies_anonymizer_protocol(session):
    assert isinstance(_pseudo(session), Anonymizer)


def test_same_value_yields_same_pseudonym(session):
    result = _pseudo(session).anonymize(f"{PII_BSN} en nogmaals {PII_BSN}")
    session.commit()
    assert PII_BSN not in result.text
    pseudonyms = re.findall(r"\[BSN:[0-9a-f]{8}\]", result.text)
    assert len(pseudonyms) == 2 and len(set(pseudonyms)) == 1


def test_roundtrip_and_audit_logged(session):
    doc = register(session, "d")
    session.commit()
    result = _pseudo(session).anonymize(
        f"BSN {PII_BSN} IBAN {PII_IBAN} mail {PII_EMAIL}"
    )
    session.commit()
    for secret in (PII_BSN, PII_IBAN, PII_EMAIL):
        assert secret not in result.text

    restored = deanonymize(
        session, doc.id, result.text,
        StubKeyProvider("pass"), PostgresMappingStore(session), actor="mark",
    )
    session.commit()
    for secret in (PII_BSN, PII_IBAN, PII_EMAIL):
        assert secret in restored

    record = session.execute(
        select(AuditRecord).where(AuditRecord.step == "deanonymize")
    ).scalar_one()
    assert record.payload["actor"] == "mark"
    for secret in (PII_BSN, PII_IBAN, PII_EMAIL):
        assert secret not in str(record.payload)  # pseudonyms only, never clear
    ok, bad = audit.verify_chain(session)
    assert ok is True and bad is None


def test_injectable_into_pipeline(session, born_digital_pii_pdf, mem_index,
                                  fake_embedder, mem_store):
    doc = ingest(session, mem_store, born_digital_pii_pdf)
    session.commit()
    final = process(session, doc.id, mem_store,
                    anonymizer=_pseudo(session), search_index=mem_index,
                    embedder=fake_embedder)
    session.commit()
    assert final == State.INDEXED

    stored = get_anonymized_text(session, doc.id)
    for secret in (PII_BSN, PII_IBAN, PII_EMAIL):
        assert secret not in stored
    assert "[BSN:" in stored  # keyed pseudonym, not the plain [BSN] placeholder

    restored = deanonymize(
        session, doc.id, stored,
        StubKeyProvider("pass"), PostgresMappingStore(session), actor="index",
    )
    for secret in (PII_BSN, PII_IBAN, PII_EMAIL):
        assert secret in restored
