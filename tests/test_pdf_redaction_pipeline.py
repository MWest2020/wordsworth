"""Box map computed inside `process`/`reanonymize` (pdf-redaction). DB-backed:
these run against a real Postgres and skip locally without one, like the
other DB integration tests."""
from __future__ import annotations

from sqlalchemy import select

from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.models import AuditRecord, BoxMap
from wordsworth.pdf_redaction import compute_box_map
from wordsworth.pipeline import ingest, process, reanonymize
from wordsworth.pseudonymizer import Pseudonymizer

PII_BSN = "123456782"
PII_IBAN = "NL91ABNA0417164300"
PII_EMAIL = "jan.jansen@haarlem.nl"


def test_process_with_key_provider_computes_a_box_map(
    session_factory, mem_store, mem_index, fake_embedder, born_digital_pii_pdf,
):
    kp = InMemoryKeyProvider()
    with session_factory() as s:
        doc = ingest(s, mem_store, born_digital_pii_pdf)
        s.commit()
        process(s, doc.id, mem_store,
                anonymizer=Pseudonymizer(kp, PostgresMappingStore(s)),
                search_index=mem_index, embedder=fake_embedder,
                key_provider=kp, mapping_store=PostgresMappingStore(s))
        s.commit()
        box_map = s.get(BoxMap, doc.id)
        assert box_map is not None
        assert box_map.boxes
        for row in box_map.boxes:
            assert set(row) == {"page", "rect", "token"}
            assert PII_BSN not in str(row)
            assert PII_EMAIL not in str(row)
        assert any(row["token"].startswith("[BSN:") for row in box_map.boxes)
        assert any(row["token"].startswith("[EMAIL:") for row in box_map.boxes)


def test_process_without_key_provider_leaves_no_box_map(
    session_factory, mem_store, mem_index, fake_embedder, born_digital_pii_pdf,
):
    kp = InMemoryKeyProvider()
    with session_factory() as s:
        doc = ingest(s, mem_store, born_digital_pii_pdf)
        s.commit()
        process(s, doc.id, mem_store,
                anonymizer=Pseudonymizer(kp, PostgresMappingStore(s)),
                search_index=mem_index, embedder=fake_embedder)
        s.commit()
        assert s.get(BoxMap, doc.id) is None


def test_reanonymize_recomputes_the_box_map(
    session_factory, mem_store, mem_index, fake_embedder, born_digital_pii_pdf,
):
    kp = InMemoryKeyProvider()
    with session_factory() as s:
        doc = ingest(s, mem_store, born_digital_pii_pdf)
        s.commit()
        process(s, doc.id, mem_store,
                anonymizer=Pseudonymizer(kp, PostgresMappingStore(s)),
                search_index=mem_index, embedder=fake_embedder,
                key_provider=kp, mapping_store=PostgresMappingStore(s))
        s.commit()
        first_hash = s.get(BoxMap, doc.id).boxmap_hash

        reanonymize(s, doc.id, mem_store,
                   anonymizer=Pseudonymizer(kp, PostgresMappingStore(s)),
                   search_index=mem_index, embedder=fake_embedder,
                   key_provider=kp, mapping_store=PostgresMappingStore(s))
        s.commit()
        second = s.get(BoxMap, doc.id)
        assert second is not None
        # Same values, same (absent) lists -- re-running yields the identical map.
        assert second.boxmap_hash == first_hash


def test_value_not_located_writes_audit_and_persists_no_box_map(
    session_factory, mem_store, born_digital_pii_pdf,
):
    kp = InMemoryKeyProvider()
    with session_factory() as s:
        doc = ingest(s, mem_store, born_digital_pii_pdf)
        s.commit()
        mapping_store = PostgresMappingStore(s)
        anonymizer = Pseudonymizer(kp, mapping_store)
        # The BSN occurs twice in the text the anonymizer runs over (the token
        # is therefore registered twice in the anonymised text), but
        # born_digital_pii_pdf's own positioned text only has it once —
        # the scenario the fail-hard count check exists for.
        plain = (f"Aanvrager BSN {PII_BSN} IBAN {PII_IBAN} email {PII_EMAIL} "
                 f"BSN {PII_BSN} einde.")
        result = anonymizer.anonymize(plain)
        from wordsworth import pseudonym_registry

        pseudonym_registry.register(s, doc.id, result.text)
        s.flush()

        box_map = compute_box_map(
            s, doc.id, born_digital_pii_pdf, result.text,
            result.lists_hash, kp, mapping_store,
        )
        assert box_map is None
        s.commit()

        rec = s.execute(
            select(AuditRecord).where(AuditRecord.document_id == doc.id,
                                      AuditRecord.step == "value-not-located")
        ).scalar_one()
        assert rec.payload["pii_type"] == "BSN"
        assert rec.payload["in_anonymized"] == 2
        assert rec.payload["in_positioned"] == 1
        assert PII_BSN not in str(rec.payload)
        assert s.get(BoxMap, doc.id) is None
