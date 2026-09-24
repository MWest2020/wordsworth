"""Key-gated reveal endpoint POST /documents/{id}/reveal (add-reveal-api).

DB-backed (reveal reads the stored pseudonymised text + mappings and appends an
audited access event), so these run in CI against a real Postgres and skip
locally without a DB — as the other DB integration tests do."""
from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from wordsworth import audit
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
    """Ingest+pseudonymise one PII doc; return (shared key provider, doc id)."""
    kp = InMemoryKeyProvider()
    with session_factory() as s:
        doc = ingest(s, mem_store, pdf)
        s.commit()
        process(s, doc.id, mem_store,
                anonymizer=Pseudonymizer(kp, PostgresMappingStore(s)),
                search_index=mem_index, embedder=fake_embedder)
        s.commit()
        return kp, doc.id


def _client(session_factory, kp, gs):
    return TestClient(create_app(session_factory=session_factory,
                                 key_provider=kp, grant_store=gs))


def test_reveal_only_granted_type(session_factory, mem_store, mem_index,
                                  fake_embedder, born_digital_pii_pdf):
    kp, doc_id = _prepare(session_factory, mem_store, mem_index, fake_embedder,
                          born_digital_pii_pdf)
    gs = InMemoryGrantStore()
    grant = gs.issue("agent-x", ["EMAIL"], actor="mark", document_id=doc_id)

    r = _client(session_factory, kp, gs).post(
        f"/documents/{doc_id}/reveal",
        json={"grant_id": grant.grant_id, "types": ["EMAIL", "BSN"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert PII_EMAIL in body["revealed_text"]      # granted → revealed
    assert PII_BSN not in body["revealed_text"]     # withheld → stays token
    assert "[BSN:" in body["revealed_text"]
    assert body["revealed_types"] == ["EMAIL"]
    assert "BSN" in body["withheld_types"]
    assert body["grant_id"] == grant.grant_id


def test_reveal_defaults_to_grant_types(session_factory, mem_store, mem_index,
                                        fake_embedder, born_digital_pii_pdf):
    kp, doc_id = _prepare(session_factory, mem_store, mem_index, fake_embedder,
                          born_digital_pii_pdf)
    gs = InMemoryGrantStore()
    grant = gs.issue("agent-x", ["EMAIL"], actor="mark", document_id=doc_id)
    # no explicit types → reveal exactly what the grant allows
    r = _client(session_factory, kp, gs).post(
        f"/documents/{doc_id}/reveal", json={"grant_id": grant.grant_id})
    assert r.status_code == 200
    assert r.json()["revealed_types"] == ["EMAIL"]


def test_revoked_grant_forbidden(session_factory, mem_store, mem_index,
                                 fake_embedder, born_digital_pii_pdf):
    kp, doc_id = _prepare(session_factory, mem_store, mem_index, fake_embedder,
                          born_digital_pii_pdf)
    gs = InMemoryGrantStore()
    grant = gs.issue("agent-x", ["EMAIL"], actor="mark", document_id=doc_id)
    gs.revoke(grant.grant_id, "mark")
    r = _client(session_factory, kp, gs).post(
        f"/documents/{doc_id}/reveal", json={"grant_id": grant.grant_id})
    assert r.status_code == 403


def test_unknown_grant_is_404(session_factory, mem_store, mem_index,
                              fake_embedder, born_digital_pii_pdf):
    kp, doc_id = _prepare(session_factory, mem_store, mem_index, fake_embedder,
                          born_digital_pii_pdf)
    r = _client(session_factory, kp, InMemoryGrantStore()).post(
        f"/documents/{doc_id}/reveal", json={"grant_id": "nope"})
    assert r.status_code == 404


def test_unknown_document_is_404(session_factory, mem_store, mem_index,
                                 fake_embedder, born_digital_pii_pdf):
    kp, _ = _prepare(session_factory, mem_store, mem_index, fake_embedder,
                     born_digital_pii_pdf)
    gs = InMemoryGrantStore()
    grant = gs.issue("agent-x", ["EMAIL"], actor="mark")
    r = _client(session_factory, kp, gs).post(
        f"/documents/{uuid4()}/reveal", json={"grant_id": grant.grant_id})
    assert r.status_code == 404


def test_grant_for_other_document_forbidden(session_factory, mem_store, mem_index,
                                            fake_embedder, born_digital_pii_pdf):
    kp, doc_id = _prepare(session_factory, mem_store, mem_index, fake_embedder,
                          born_digital_pii_pdf)
    gs = InMemoryGrantStore()
    grant = gs.issue("agent-x", ["EMAIL"], actor="mark", document_id=uuid4())
    r = _client(session_factory, kp, gs).post(
        f"/documents/{doc_id}/reveal", json={"grant_id": grant.grant_id})
    assert r.status_code == 403


def test_reveal_is_audited(session_factory, mem_store, mem_index, fake_embedder,
                           born_digital_pii_pdf):
    kp, doc_id = _prepare(session_factory, mem_store, mem_index, fake_embedder,
                          born_digital_pii_pdf)
    gs = InMemoryGrantStore()
    grant = gs.issue("agent-x", ["EMAIL"], actor="mark", document_id=doc_id)
    _client(session_factory, kp, gs).post(
        f"/documents/{doc_id}/reveal", json={"grant_id": grant.grant_id})

    with session_factory() as s:
        rec = s.execute(
            select(AuditRecord).where(AuditRecord.step == "deanonymize")
        ).scalar_one()
        assert rec.payload["actor"] == "agent-x"          # grant recipient
        assert rec.payload["grant_id"] == grant.grant_id  # access attributed to grant
        assert rec.payload["types"] == ["EMAIL"]
        assert PII_EMAIL not in str(rec.payload)          # never clear values
        ok, bad = audit.verify_chain(s)
        assert ok is True and bad is None


def test_authorized_is_not_the_same_as_resolved(session_factory, mem_store,
                                                mem_index, fake_embedder,
                                                born_digital_pii_pdf):
    """Een toegestaan type dat niets oplevert mag niet als 'onthuld' klinken.

    Het antwoord zei tot nu toe `revealed_types: [...]` en bedoelde daarmee
    "wat de grant toestond". Het auditveld `types` bedoelde "wat er werkelijk
    uit de mappingstore kwam". Bijna dezelfde naam, twee dingen — en wie ze
    naast elkaar legde concludeerde dat het spoor gaten had.

    Hier staat PHONE_NUMBER wel in de grant maar niet in het document. Dan
    hoort `authorized_types` hem te noemen, `resolved_types` niet, en hoort
    `resolved_types` letterlijk gelijk te zijn aan wat de auditregel noteerde.
    """
    kp, doc_id = _prepare(session_factory, mem_store, mem_index, fake_embedder,
                          born_digital_pii_pdf)
    gs = InMemoryGrantStore()
    grant = gs.issue("agent-x", ["EMAIL", "PHONE_NUMBER"], actor="mark",
                     document_id=doc_id)

    r = _client(session_factory, kp, gs).post(
        f"/documents/{doc_id}/reveal",
        json={"grant_id": grant.grant_id, "types": ["EMAIL", "PHONE_NUMBER"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["authorized_types"] == ["EMAIL", "PHONE_NUMBER"]
    assert body["resolved_types"] == ["EMAIL"]
    assert body["withheld_types"] == []          # beide mochten, één leverde
    assert body["revealed_types"] == body["authorized_types"], "oude naam blijft"

    with session_factory() as s:
        payload = s.execute(
            select(AuditRecord.payload)
            .where(AuditRecord.document_id == doc_id,
                   AuditRecord.step == "deanonymize")
            .order_by(AuditRecord.seq.desc()).limit(1)
        ).scalar_one()
    assert payload["types"] == body["resolved_types"]
    assert payload["requested_types"] == body["authorized_types"]


def test_reveal_on_a_retired_copy_is_refused_and_names_the_survivor(legacy_copies, session_factory, mem_store, mem_index, fake_embedder, born_digital_pii_pdf):
    """one-document-per-object: a copy is not a second door to the same
    pseudonyms. The survivor still reveals; the copy says where to go."""
    from wordsworth.pipeline import register
    from wordsworth.supersession import supersede

    kp, doc_id = _prepare(session_factory, mem_store, mem_index, fake_embedder,
                          born_digital_pii_pdf)
    with session_factory() as s:
        from wordsworth.models import Document
        copy = register(s, s.get(Document, doc_id).object_key)
        s.flush()
        supersede(s, copy.id, doc_id, actor="dedupe")
        s.commit()
        copy_id = copy.id
    gs = InMemoryGrantStore()
    on_copy = gs.issue("agent-x", ["EMAIL"], actor="mark", document_id=copy_id)
    on_survivor = gs.issue("agent-x", ["EMAIL"], actor="mark", document_id=doc_id)
    c = _client(session_factory, kp, gs)
    r = c.post(f"/documents/{copy_id}/reveal", json={"grant_id": on_copy.grant_id})
    assert r.status_code == 409 and str(doc_id) in r.json()["detail"]
    assert c.post(f"/documents/{doc_id}/reveal",
                  json={"grant_id": on_survivor.grant_id}).status_code == 200
