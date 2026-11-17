"""reveal-authorize-first (#487): the grant decides before anything about the
document is read, and every refusal to a caller the grant does not cover
looks the same -- the uniform refusal, never a 404, a 410 or a 409 naming a
survivor. DB-backed, like the other reveal integration tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select

from wordsworth import roles
from wordsworth.api import create_app
from wordsworth.audit import verify_chain
from wordsworth.deletion import delete_document
from wordsworth.grants import ACTIVE, InMemoryGrantStore, PostgresGrantStore
from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.models import AuditRecord, GrantRecord, KeyLifecycleEvent
from wordsworth.pipeline import ingest, process, register
from wordsworth.pseudonymizer import Pseudonymizer
from wordsworth.supersession import supersede

UNIFORM_REFUSAL = {"detail": "grant not applicable"}
ROUTES = ("reveal", "reveal.pdf")
_READ_TABLES = ("documents", "audit_records", "document_texts",
               "document_pseudonyms", "pii_mappings", "box_maps",
               "document_summaries", "dossier_documents")


def _prepare(session_factory, mem_store, mem_index, fake_embedder, pdf):
    """Ingest+pseudonymise one PII doc, with a box map (reveal.pdf needs one)."""
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


def test_grant_that_does_not_apply_reads_nothing_about_the_document(
        session_factory, mem_store, mem_index, fake_embedder, born_digital_pii_pdf):
    kp, doc_id = _prepare(session_factory, mem_store, mem_index, fake_embedder,
                          born_digital_pii_pdf)
    gs = InMemoryGrantStore()
    revoked = gs.issue("agent-x", ["EMAIL"], actor="mark", document_id=doc_id)
    gs.revoke(revoked.grant_id, "mark")
    expired = gs.issue("agent-x", ["EMAIL"], actor="mark", document_id=doc_id,
                       expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    other_doc = gs.issue("agent-x", ["EMAIL"], actor="mark", document_id=uuid4())
    for_other = gs.issue("someone-else", ["EMAIL"], actor="mark", document_id=doc_id)

    client = TestClient(create_app(session_factory=session_factory, store=mem_store,
                                   key_provider=kp, grant_store=gs,
                                   api_keys={"agent-x-key": "agent-x"}))
    headers = {"X-API-Key": "agent-x-key"}

    with session_factory() as probe:
        engine = probe.get_bind()
    statements: list[str] = []

    def _listener(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", _listener)
    try:
        grant_ids = ("no-such-grant", revoked.grant_id, expired.grant_id,
                    other_doc.grant_id, for_other.grant_id)
        for route in ROUTES:
            for grant_id in grant_ids:
                statements.clear()
                r = client.post(f"/documents/{doc_id}/{route}",
                                json={"grant_id": grant_id}, headers=headers)
                assert r.status_code == 403, (route, grant_id, r.text)
                read = [s for s in statements
                       if any(t in s.lower() for t in _READ_TABLES)]
                assert read == [], (route, grant_id, read)
    finally:
        event.remove(engine, "before_cursor_execute", _listener)


def test_unscoped_grant_from_another_domain_hears_nothing_about_deletion_or_supersession(
        session_factory, mem_store, mem_index, fake_embedder, born_digital_pii_pdf):
    kp, doc_id = _prepare(session_factory, mem_store, mem_index, fake_embedder,
                          born_digital_pii_pdf)
    with session_factory() as s:
        other_a = register(s, "documents/" + "aa" * 32, domain="b")
        other_b = register(s, "documents/" + "bb" * 32, domain="b")
        s.flush()
        supersede(s, other_a.id, other_b.id, actor="dedupe",
                 as_object=other_b.object_key)
        deleted_doc = register(s, "documents/" + "cc" * 32, domain="b")
        s.flush()
        delete_document(s, deleted_doc.id, mem_store, mem_index, actor="tester")
        s.commit()
        superseded_id, deleted_id = other_a.id, deleted_doc.id

    gs = InMemoryGrantStore()
    unscoped_a = gs.issue("agent-x", ["EMAIL"], actor="mark", domain="a")
    client = TestClient(create_app(session_factory=session_factory, store=mem_store,
                                   key_provider=kp, grant_store=gs,
                                   allow_global_grants=True))
    for route in ROUTES:
        for target in (superseded_id, deleted_id):
            r = client.post(f"/documents/{target}/{route}",
                            json={"grant_id": unscoped_a.grant_id})
            assert r.status_code == 403, (route, target, r.text)
            assert r.json() == UNIFORM_REFUSAL

    # Same again, this time the exception is a `beheerder` role grant rather
    # than the deployment-wide flag.
    with session_factory() as s:
        from wordsworth.key_audit_pg import PostgresKeyLifecycleAudit
        roles.create(s, roles.ADMIN, ["EMAIL"], actor="mark",
                    audit=PostgresKeyLifecycleAudit(s))
        s.add(GrantRecord(
            grant_id="admin-grant-a", recipient="agent-y", allowed_types=[],
            document_id=None, status=ACTIVE,
            created_at=datetime.now(timezone.utc), revoked_at=None,
            expires_at=None, actor="mark", domain="a", role=roles.ADMIN))
        s.commit()
    client2 = TestClient(create_app(session_factory=session_factory, store=mem_store,
                                    key_provider=kp,
                                    grant_store_factory=PostgresGrantStore))
    for route in ROUTES:
        for target in (superseded_id, deleted_id):
            r = client2.post(f"/documents/{target}/{route}",
                             json={"grant_id": "admin-grant-a"})
            assert r.status_code == 403, (route, target, r.text)
            assert r.json() == UNIFORM_REFUSAL


def test_unknown_document_and_a_document_outside_scope_look_alike(
        session_factory, mem_store, mem_index, fake_embedder, born_digital_pii_pdf):
    kp, doc_id = _prepare(session_factory, mem_store, mem_index, fake_embedder,
                          born_digital_pii_pdf)
    gs = InMemoryGrantStore()
    grant = gs.issue("ontvanger", ["EMAIL"], actor="mark", document_id=doc_id)
    client = TestClient(create_app(session_factory=session_factory, store=mem_store,
                                   key_provider=kp, grant_store=gs,
                                   api_keys={"derde-key": "derde"}))
    for route in ROUTES:
        unknown = client.post(f"/documents/{uuid4()}/{route}",
                              json={"grant_id": grant.grant_id},
                              headers={"X-API-Key": "derde-key"})
        outside_scope = client.post(f"/documents/{doc_id}/{route}",
                                    json={"grant_id": grant.grant_id},
                                    headers={"X-API-Key": "derde-key"})
        assert unknown.status_code == outside_scope.status_code == 403
        assert unknown.json() == outside_scope.json() == UNIFORM_REFUSAL


def test_superseded_document_does_not_name_its_survivor_to_an_uncovered_caller(
        legacy_copies, mem_store, mem_index, fake_embedder, born_digital_pii_pdf):
    """Also document-lifecycle "Reveal on a copy by a caller the grant does
    not cover": the uniform refusal, no survivor named."""
    session_factory = legacy_copies
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
    elsewhere = gs.issue("agent-x", ["EMAIL"], actor="mark", document_id=uuid4())
    client = TestClient(create_app(session_factory=session_factory, store=mem_store,
                                   key_provider=kp, grant_store=gs))
    r = client.post(f"/documents/{copy_id}/reveal",
                    json={"grant_id": elsewhere.grant_id})
    assert r.status_code == 403
    assert r.json() == UNIFORM_REFUSAL
    assert str(doc_id) not in r.text and "superseded" not in r.text
    r = client.post(f"/documents/{copy_id}/reveal.pdf",
                    json={"grant_id": elsewhere.grant_id})
    assert r.status_code == 403
    assert r.json() == UNIFORM_REFUSAL
    assert str(doc_id) not in r.text and "superseded" not in r.text


def test_covered_caller_is_told_the_document_is_deleted(
        session_factory, mem_store, mem_index, fake_embedder, born_digital_pii_pdf):
    kp, doc_id = _prepare(session_factory, mem_store, mem_index, fake_embedder,
                          born_digital_pii_pdf)
    with session_factory() as s:
        delete_document(s, doc_id, mem_store, mem_index, actor="tester")
        s.commit()

    gs = InMemoryGrantStore()
    unscoped = gs.issue("agent-x", ["EMAIL"], actor="mark")
    client = TestClient(create_app(session_factory=session_factory, store=mem_store,
                                   key_provider=kp, grant_store=gs,
                                   allow_global_grants=True))
    for route in ROUTES:
        r = client.post(f"/documents/{doc_id}/{route}",
                        json={"grant_id": unscoped.grant_id})
        assert r.status_code == 410, (route, r.text)
    with session_factory() as s:
        assert s.execute(select(AuditRecord).where(
            AuditRecord.document_id == doc_id, AuditRecord.step == "deanonymize"
        )).first() is None


def test_covered_caller_is_told_document_not_yet_deidentified(
        session_factory, mem_store):
    with session_factory() as s:
        doc = register(s, "documents/" + "dd" * 32)
        s.flush()
        s.commit()
        doc_id = doc.id
    gs = InMemoryGrantStore()
    grant = gs.issue("agent-x", ["EMAIL"], actor="mark", document_id=doc_id)
    client = TestClient(create_app(session_factory=session_factory,
                                   key_provider=InMemoryKeyProvider(),
                                   grant_store=gs))
    r = client.post(f"/documents/{doc_id}/reveal", json={"grant_id": grant.grant_id})
    assert r.status_code == 409
    assert "not yet de-identified" in r.json()["detail"]


def test_covered_caller_without_required_credential_hears_nothing(
        session_factory, mem_store, mem_index, fake_embedder, born_digital_pii_pdf):
    kp, doc_id = _prepare(session_factory, mem_store, mem_index, fake_embedder,
                          born_digital_pii_pdf)
    with session_factory() as s:
        other_a = register(s, "documents/" + "ee" * 32)
        other_b = register(s, "documents/" + "ff" * 32)
        s.flush()
        supersede(s, other_a.id, other_b.id, actor="dedupe",
                 as_object=other_b.object_key)
        s.commit()
        superseded_id = other_a.id

    gs = InMemoryGrantStore()
    on_superseded = gs.issue("agent-x", ["EMAIL"], actor="mark",
                             document_id=superseded_id)
    on_deleted_target = gs.issue("agent-x", ["EMAIL"], actor="mark",
                                 document_id=doc_id)
    with session_factory() as s:
        delete_document(s, doc_id, mem_store, mem_index, actor="tester")
        s.commit()

    key = ec.generate_private_key(ec.SECP256R1())
    client = TestClient(create_app(session_factory=session_factory, store=mem_store,
                                   key_provider=kp, grant_store=gs,
                                   vc_public_key=key.public_key(), vc_required=True))
    for route in ROUTES:
        r = client.post(f"/documents/{superseded_id}/{route}",
                        json={"grant_id": on_superseded.grant_id})
        assert r.status_code == 403 and "vc rejected" in r.json()["detail"], r.text
        r = client.post(f"/documents/{doc_id}/{route}",
                        json={"grant_id": on_deleted_target.grant_id})
        assert r.status_code == 403 and "vc rejected" in r.json()["detail"], r.text


def test_refusal_writes_no_audit_record(
        session_factory, mem_store, mem_index, fake_embedder, born_digital_pii_pdf):
    kp, doc_id = _prepare(session_factory, mem_store, mem_index, fake_embedder,
                          born_digital_pii_pdf)
    client = TestClient(create_app(session_factory=session_factory, store=mem_store,
                                   key_provider=kp, grant_store=InMemoryGrantStore()))
    with session_factory() as s:
        before_audit = s.execute(select(func.count(AuditRecord.seq))).scalar_one()
        before_keys = s.execute(select(func.count(KeyLifecycleEvent.seq))).scalar_one()
    for route in ROUTES:
        r = client.post(f"/documents/{doc_id}/{route}",
                        json={"grant_id": "no-such-grant"})
        assert r.status_code == 403
    with session_factory() as s:
        after_audit = s.execute(select(func.count(AuditRecord.seq))).scalar_one()
        after_keys = s.execute(select(func.count(KeyLifecycleEvent.seq))).scalar_one()
        ok, bad = verify_chain(s)
    assert (before_audit, before_keys) == (after_audit, after_keys)
    assert ok is True and bad is None


def test_refusal_logs_nothing_about_its_cause(
        session_factory, mem_store, mem_index, fake_embedder, born_digital_pii_pdf,
        caplog):
    kp, doc_id = _prepare(session_factory, mem_store, mem_index, fake_embedder,
                          born_digital_pii_pdf)
    with session_factory() as s:
        other_a = register(s, "documents/" + "11" * 32)
        other_b = register(s, "documents/" + "22" * 32)
        s.flush()
        supersede(s, other_a.id, other_b.id, actor="dedupe",
                 as_object=other_b.object_key)
        deleted_doc = register(s, "documents/" + "33" * 32)
        s.flush()
        delete_document(s, deleted_doc.id, mem_store, mem_index, actor="tester")
        s.commit()
        superseded_id, deleted_id = other_a.id, deleted_doc.id

    gs = InMemoryGrantStore()
    elsewhere = gs.issue("agent-x", ["EMAIL"], actor="mark", document_id=uuid4())
    client = TestClient(create_app(session_factory=session_factory, store=mem_store,
                                   key_provider=kp, grant_store=gs))
    targets = (uuid4(), superseded_id, deleted_id, doc_id)
    # The requested document's own id is unavoidably in the access log (the
    # path); the survivor's id and the cause words are what must not leak.
    forbidden_words = ("unknown", "superseded", "deleted", str(other_b.id))
    for route in ROUTES:
        for target in targets:
            caplog.clear()
            with caplog.at_level("DEBUG"):
                r = client.post(f"/documents/{target}/{route}",
                                json={"grant_id": elsewhere.grant_id})
            assert r.status_code == 403
            text = "\n".join(rec.getMessage() for rec in caplog.records)
            for word in forbidden_words:
                assert word not in text, (route, target, word, text)
