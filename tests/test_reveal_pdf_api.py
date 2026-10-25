"""POST /documents/{id}/reveal.pdf (pdf-redaction). DB-backed: runs against a
real Postgres and skips locally without one, like the other DB integration
tests."""
from __future__ import annotations

import io

import pypdf
from fastapi.testclient import TestClient
from sqlalchemy import select

from wordsworth.api import create_app
from wordsworth.grants import InMemoryGrantStore
from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.models import AuditRecord
from wordsworth.pipeline import ingest, process
from wordsworth.pseudonymizer import Pseudonymizer

PII_BSN = "123456782"
PII_EMAIL = "jan.jansen@haarlem.nl"


def _prepare(session_factory, mem_store, mem_index, fake_embedder, pdf):
    kp = InMemoryKeyProvider()
    with session_factory() as s:
        doc = ingest(s, mem_store, pdf)
        s.commit()
        process(s, doc.id, mem_store,
                anonymizer=Pseudonymizer(kp, PostgresMappingStore(s)),
                search_index=mem_index, embedder=fake_embedder,
                key_provider=kp, mapping_store=PostgresMappingStore(s))
        s.commit()
        return kp, doc.id


def _client(session_factory, mem_store, kp, gs):
    return TestClient(create_app(session_factory=session_factory, store=mem_store,
                                 key_provider=kp, grant_store=gs))


def test_granted_type_is_drawn_other_stays_labelled(
    session_factory, mem_store, mem_index, fake_embedder, born_digital_pii_pdf,
):
    kp, doc_id = _prepare(session_factory, mem_store, mem_index, fake_embedder,
                          born_digital_pii_pdf)
    gs = InMemoryGrantStore()
    grant = gs.issue("agent-x", ["EMAIL"], actor="mark", document_id=doc_id)

    r = _client(session_factory, mem_store, kp, gs).post(
        f"/documents/{doc_id}/reveal.pdf",
        json={"grant_id": grant.grant_id, "types": ["EMAIL", "BSN"]},
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    text = pypdf.PdfReader(io.BytesIO(r.content)).pages[0].extract_text()
    assert PII_EMAIL in text       # granted -> drawn in clear
    assert PII_BSN not in text     # withheld -> stays boxed/labelled
    assert "[BSN 1]" in text or "[BSN" in text  # the label is still present


def test_never_cached(session_factory, mem_store, mem_index, fake_embedder,
                      born_digital_pii_pdf):
    kp, doc_id = _prepare(session_factory, mem_store, mem_index, fake_embedder,
                          born_digital_pii_pdf)
    gs = InMemoryGrantStore()
    grant = gs.issue("agent-x", ["EMAIL"], actor="mark", document_id=doc_id)
    _client(session_factory, mem_store, kp, gs).post(
        f"/documents/{doc_id}/reveal.pdf", json={"grant_id": grant.grant_id})
    assert not any(k.startswith(f"redacted/{doc_id}/") for k in mem_store._data)


def test_audited_as_deanonymize_view_pdf_no_clear_value(
    session_factory, mem_store, mem_index, fake_embedder, born_digital_pii_pdf,
):
    kp, doc_id = _prepare(session_factory, mem_store, mem_index, fake_embedder,
                          born_digital_pii_pdf)
    gs = InMemoryGrantStore()
    grant = gs.issue("agent-x", ["EMAIL"], actor="mark", document_id=doc_id)
    _client(session_factory, mem_store, kp, gs).post(
        f"/documents/{doc_id}/reveal.pdf", json={"grant_id": grant.grant_id})

    with session_factory() as s:
        rec = s.execute(
            select(AuditRecord).where(AuditRecord.document_id == doc_id,
                                      AuditRecord.step == "deanonymize")
        ).scalar_one()
    assert rec.payload["view"] == "pdf"
    assert rec.payload["types"] == ["EMAIL"]
    assert PII_EMAIL not in str(rec.payload)
    assert PII_BSN not in str(rec.payload)


def test_revoked_grant_forbidden(session_factory, mem_store, mem_index, fake_embedder,
                                 born_digital_pii_pdf):
    kp, doc_id = _prepare(session_factory, mem_store, mem_index, fake_embedder,
                          born_digital_pii_pdf)
    gs = InMemoryGrantStore()
    grant = gs.issue("agent-x", ["EMAIL"], actor="mark", document_id=doc_id)
    gs.revoke(grant.grant_id, "mark")
    r = _client(session_factory, mem_store, kp, gs).post(
        f"/documents/{doc_id}/reveal.pdf", json={"grant_id": grant.grant_id})
    assert r.status_code == 403
