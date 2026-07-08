from sqlalchemy import select

from wordsworth import audit
from wordsworth.anonymizer import AnonymizationResult
from wordsworth.models import AuditRecord, DocumentText
from wordsworth.pipeline import get_anonymized_text, process, register
from wordsworth.states import State

# Same values the born_digital_pii_pdf fixture embeds.
PII_BSN = "123456782"
PII_IBAN = "NL91ABNA0417164300"
PII_EMAIL = "jan.jansen@haarlem.nl"


def _anonymize_payload(session, document_id):
    return session.execute(
        select(AuditRecord.payload).where(
            AuditRecord.document_id == document_id, AuditRecord.step == "anonymize"
        )
    ).scalar_one()


def test_pii_document_ends_pii_free_and_indexed(session, born_digital_pii_pdf,
                                                mem_index, fake_embedder):
    doc = register(session, "pii")
    session.commit()
    final = process(session, doc.id, born_digital_pii_pdf, search_index=mem_index,
                    embedder=fake_embedder)
    session.commit()

    assert final == State.INDEXED
    stored = get_anonymized_text(session, doc.id)
    for secret in (PII_BSN, PII_IBAN, PII_EMAIL):
        assert secret not in stored
    assert "[BSN]" in stored and "[IBAN]" in stored and "[EMAIL]" in stored
    assert _anonymize_payload(session, doc.id) == {"email": 1, "iban": 1, "bsn": 1}

    ok, bad = audit.verify_chain(session)
    assert ok is True and bad is None


def test_injected_anonymizer_is_used(session, born_digital_pdf, mem_index, fake_embedder):
    class MarkerAnonymizer:
        def anonymize(self, text):
            return AnonymizationResult(text="MARKER", counts={"custom": 7})

    doc = register(session, "inject")
    session.commit()
    process(session, doc.id, born_digital_pdf, anonymizer=MarkerAnonymizer(),
            search_index=mem_index, embedder=fake_embedder)
    session.commit()

    assert get_anonymized_text(session, doc.id) == "MARKER"
    assert _anonymize_payload(session, doc.id) == {"custom": 7}


def test_only_anonymized_text_is_stored(session, born_digital_pii_pdf, mem_index,
                                        fake_embedder):
    doc = register(session, "onlyanon")
    session.commit()
    process(session, doc.id, born_digital_pii_pdf, search_index=mem_index,
            embedder=fake_embedder)
    session.commit()
    rows = session.execute(select(DocumentText)).scalars().all()
    assert len(rows) == 1
    assert rows[0].document_id == doc.id
