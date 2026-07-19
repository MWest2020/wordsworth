"""OpenAnonymiser driver: protocol, composition, real CPU inference, failure.

The ``real_driver`` fixture runs the actual local engine (spaCy nl_core_news_lg
via Presidio, CPU). The model load is slow, so it is session-scoped and the
upstream engines are process-level singletons — loaded once for the suite.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from wordsworth.anonymizer import Anonymizer
from wordsworth.models import AuditRecord, DocumentText
from wordsworth.openanonymiser_driver import (
    AnonymizationEngineError,
    OpenAnonymiserAnonymizer,
)
from wordsworth.pipeline import get_anonymized_text, ingest, process
from wordsworth.states import State

PII_BSN = "123456782"
PII_IBAN = "NL91ABNA0417164300"
PII_EMAIL = "jan.jansen@haarlem.nl"
PII_NAME = "Jan Jansen"


@pytest.fixture(scope="session")
def real_driver() -> OpenAnonymiserAnonymizer:
    return OpenAnonymiserAnonymizer()  # real local engine, loaded on first call


def _broken_engine(text: str) -> tuple[str, dict[str, int]]:
    raise ConnectionError("engine down")


# --- 2.1 protocol + injectable into process() --------------------------------

def test_satisfies_anonymizer_protocol():
    assert isinstance(OpenAnonymiserAnonymizer(), Anonymizer)


def test_injectable_into_process(session, born_digital_pii_pdf, mem_index,
                                 fake_embedder, mem_store, real_driver):
    doc = ingest(session, mem_store, born_digital_pii_pdf)
    session.commit()
    final = process(session, doc.id, mem_store, anonymizer=real_driver,
                    search_index=mem_index, embedder=fake_embedder)
    session.commit()

    assert final == State.INDEXED
    stored = get_anonymized_text(session, doc.id)
    for secret in (PII_BSN, PII_IBAN, PII_EMAIL):
        assert secret not in stored
    payload = session.execute(
        select(AuditRecord.payload).where(
            AuditRecord.document_id == doc.id, AuditRecord.step == "anonymize"
        )
    ).scalar_one()
    assert payload["bsn"] == 1 and payload["iban"] == 1 and payload["email"] == 1


# --- 2.2 entity PII redacted, structured PII still redacted -------------------

def test_personal_name_and_structured_pii_redacted(real_driver):
    text = (f"{PII_NAME} woont in Amsterdam. BSN {PII_BSN}, "
            f"IBAN {PII_IBAN}, mail {PII_EMAIL}.")
    result = real_driver.anonymize(text)

    for secret in (PII_NAME, PII_BSN, PII_IBAN, PII_EMAIL):
        assert secret not in result.text
    assert "<PERSON>" in result.text
    assert "[BSN]" in result.text and "[IBAN]" in result.text and "[EMAIL]" in result.text
    assert result.counts["bsn"] == 1 and result.counts["iban"] == 1
    assert result.counts["email"] == 1 and result.counts["person"] >= 1


def test_result_carries_no_reverse_mapping(real_driver):
    result = real_driver.anonymize(f"{PII_NAME}, BSN {PII_BSN}")
    assert set(vars(result)) == {"text", "counts"}  # irreversible: text + counts only


def test_deterministic_runs_first_and_counts_merge():
    def engine(text: str) -> tuple[str, dict[str, int]]:
        # Composition order: structured PII is already gone when the engine runs.
        assert PII_BSN not in text and "[BSN]" in text
        return text.replace(PII_NAME, "<PERSON>"), {"person": 1}

    result = OpenAnonymiserAnonymizer(engine=engine).anonymize(
        f"{PII_NAME} BSN {PII_BSN}"
    )
    assert result.counts == {"bsn": 1, "iban": 0, "email": 0, "person": 1}
    assert PII_NAME not in result.text and PII_BSN not in result.text


# --- 2.3 engine failure raises, no clear-text leak ----------------------------

def test_engine_failure_raises_and_carries_no_text():
    driver = OpenAnonymiserAnonymizer(engine=_broken_engine)
    with pytest.raises(AnonymizationEngineError) as excinfo:
        driver.anonymize(f"geheim {PII_BSN} van {PII_NAME}")
    assert isinstance(excinfo.value.__cause__, ConnectionError)
    for secret in (PII_BSN, PII_NAME, "geheim"):
        assert secret not in str(excinfo.value)


def test_engine_failure_stores_and_indexes_nothing(session, born_digital_pii_pdf,
                                                   mem_index, fake_embedder,
                                                   mem_store):
    doc = ingest(session, mem_store, born_digital_pii_pdf)
    session.commit()
    with pytest.raises(AnonymizationEngineError):
        process(session, doc.id, mem_store,
                anonymizer=OpenAnonymiserAnonymizer(engine=_broken_engine),
                search_index=mem_index, embedder=fake_embedder)
    session.rollback()

    assert session.execute(select(DocumentText)).scalars().all() == []
    assert mem_index.search("Aanvrager") == []  # nothing reached the index
    anonymize_steps = session.execute(
        select(AuditRecord).where(AuditRecord.document_id == doc.id,
                                  AuditRecord.step == "anonymize")
    ).scalars().all()
    assert anonymize_steps == []
