# SPDX-License-Identifier: MIT
"""reveal-authorize-first (closes #487): both reveal routes judge the grant
before reading anything about the document, and every caller the grant does
not cover gets the same answer. DB-backed: runs against a real Postgres and
skips locally without one, like the other DB integration tests.

Callers: ``ontvanger`` (a grant's recipient) and ``derde`` (authenticated, not
the recipient). Grants live in ``PostgresGrantStore`` throughout, because that
is the store a deletion actually empties (production wiring); content is
never needed here -- every scenario below is refused, or answers 409/410,
before any text is read, so a plain ``register()`` stands in for a processed
document.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select

from wordsworth.api import create_app
from wordsworth.audit import verify_chain
from wordsworth.bootstrap import ensure_admin_role
from wordsworth.deletion import delete_document
from wordsworth.grants import PostgresGrantStore
from wordsworth.keys import InMemoryKeyProvider
from wordsworth.models import AuditRecord, KeyLifecycleEvent
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.pipeline import register
from wordsworth.search_index import InMemoryIndex
from wordsworth import roles as roles_mod
from wordsworth.supersession import supersede
from wordsworth.vc import issue_sdjwt_vc

API_KEYS = {"kontvanger": "ontvanger", "kderde": "derde"}
REFUSAL = {"detail": "grant not applicable"}
ROUTES = ["/reveal", "/reveal.pdf"]
_ID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
FORBIDDEN_TABLES = ("documents", "audit_records", "document_texts",
                   "document_pseudonyms", "pii_mappings", "box_maps",
                   "document_summaries", "dossier_documents")


def _scrub_ids(text: str) -> str:
    return _ID_RE.sub("<id>", text)


def _client(session_factory, *, store=None, allow_global_grants=None, **vc):
    return TestClient(create_app(
        session_factory=session_factory, store=store,
        key_provider=InMemoryKeyProvider(), grant_store_factory=PostgresGrantStore,
        api_keys=API_KEYS, allow_global_grants=allow_global_grants, **vc))


def _statements_during(engine, fn):
    seen = []

    def _record(conn, cursor, statement, parameters, context, executemany):
        seen.append(statement)

    event.listen(engine, "before_cursor_execute", _record)
    try:
        result = fn()
    finally:
        event.remove(engine, "before_cursor_execute", _record)
    return result, seen


def _forbidden_hits(statements):
    return [(table, stmt) for stmt in statements for table in FORBIDDEN_TABLES
           if re.search(rf"\b{table}\b", stmt)]


# --- 2.1: a grant that does not apply reads nothing about the document -----

@pytest.mark.parametrize("path", ROUTES)
@pytest.mark.parametrize("cause", [
    "unknown-grant", "revoked", "expired", "other-document", "other-recipient",
])
def test_an_uncovered_grant_reads_nothing_about_the_document(
        session_factory, path, cause):
    engine = session_factory.kw["bind"]
    with session_factory() as s:
        doc_id = register(s, "documents/" + "11" * 32).id
        other_id = register(s, "documents/" + "22" * 32).id
        s.commit()
        gs = PostgresGrantStore(s)
        if cause == "unknown-grant":
            grant_id = "no-such-grant"
        elif cause == "revoked":
            g = gs.issue("derde", ["EMAIL"], actor="t", document_id=doc_id)
            gs.revoke(g.grant_id, "t")
            grant_id = g.grant_id
        elif cause == "expired":
            g = gs.issue("derde", ["EMAIL"], actor="t", document_id=doc_id,
                         expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
            grant_id = g.grant_id
        elif cause == "other-document":
            g = gs.issue("derde", ["EMAIL"], actor="t", document_id=other_id)
            grant_id = g.grant_id
        else:
            g = gs.issue("ontvanger", ["EMAIL"], actor="t", document_id=doc_id)
            grant_id = g.grant_id
        s.commit()

    client = _client(session_factory, store=InMemoryObjectStore())
    r, statements = _statements_during(engine, lambda: client.post(
        f"/documents/{doc_id}{path}", json={"grant_id": grant_id},
        headers={"X-API-Key": "kderde"}))
    assert r.status_code == 403
    assert r.json() == REFUSAL
    assert _forbidden_hits(statements) == []


# --- 2.2 (second scenario): an unscoped grant from another domain ----------

@pytest.mark.parametrize("path", ROUTES)
@pytest.mark.parametrize("cover", ["global-flag", "admin-role"])
def test_unscoped_grant_from_another_domain_hears_nothing(
        legacy_copies, path, cover):
    session_factory = legacy_copies
    store, index = InMemoryObjectStore(), InMemoryIndex()
    with session_factory() as s:
        deleted = register(s, "documents/" + "33" * 32, domain="b")
        survivor = register(s, "documents/" + "44" * 32, domain="b")
        s.flush()
        copy = register(s, "documents/" + "44" * 32, domain="b")
        s.flush()
        supersede(s, copy.id, survivor.id, actor="t")
        s.commit()
        deleted_id, copy_id = deleted.id, copy.id
    with session_factory() as s:
        delete_document(s, deleted_id, store, index, actor="t")
        s.commit()
    with session_factory() as s:
        ensure_admin_role(s)
        kwargs = {"role": roles_mod.ADMIN} if cover == "admin-role" else {}
        grant = PostgresGrantStore(s).issue(
            "ontvanger", ["EMAIL"], actor="t", document_id=None, domain="a",
            **kwargs)
        s.commit()
        grant_id = grant.grant_id

    allow_global = cover == "global-flag"
    client = _client(session_factory, store=store, allow_global_grants=allow_global)
    for target in (deleted_id, copy_id):
        r = client.post(f"/documents/{target}{path}", json={"grant_id": grant_id},
                        headers={"X-API-Key": "kontvanger"})
        assert r.status_code == 403
        assert r.json() == REFUSAL


# --- 2.3: an unknown document and one outside the scope look alike ---------

@pytest.mark.parametrize("path", ROUTES)
def test_unknown_document_and_out_of_scope_look_alike(session_factory, path):
    with session_factory() as s:
        doc_id = register(s, "documents/" + "55" * 32).id
        grant = PostgresGrantStore(s).issue("ontvanger", ["EMAIL"], actor="t",
                                            document_id=doc_id)
        s.commit()
        grant_id = grant.grant_id
    client = _client(session_factory, store=InMemoryObjectStore())
    unknown_id = uuid4()
    answers = [client.post(f"/documents/{target}{path}", json={"grant_id": grant_id},
                           headers={"X-API-Key": "kderde"})
               for target in (unknown_id, doc_id)]
    assert [a.status_code for a in answers] == [403, 403]
    assert answers[0].json() == answers[1].json() == REFUSAL


# --- 2.4: a superseded document does not name its survivor -----------------

@pytest.mark.parametrize("path", ROUTES)
def test_superseded_document_does_not_name_its_survivor(legacy_copies, path):
    """2.4, and document-lifecycle 'Reveal on a copy by a caller the grant
    does not cover'."""
    session_factory = legacy_copies
    with session_factory() as s:
        survivor = register(s, "documents/" + "66" * 32)
        s.flush()
        copy = register(s, "documents/" + "66" * 32)
        s.flush()
        supersede(s, copy.id, survivor.id, actor="t")
        other = register(s, "documents/" + "77" * 32)
        s.flush()
        grant = PostgresGrantStore(s).issue("derde", ["EMAIL"], actor="t",
                                            document_id=other.id)
        s.commit()
        copy_id, survivor_id, grant_id = copy.id, survivor.id, grant.grant_id
    client = _client(session_factory, store=InMemoryObjectStore())
    r = client.post(f"/documents/{copy_id}{path}", json={"grant_id": grant_id},
                    headers={"X-API-Key": "kderde"})
    assert r.status_code == 403
    assert r.json() == REFUSAL
    assert str(survivor_id) not in r.text
    assert "superseded" not in r.text


# --- 2.5: a deleted document is not announced -------------------------------

@pytest.mark.parametrize("path", ROUTES)
@pytest.mark.parametrize("cause", ["unknown-grant", "removed-grant", "other-caller"])
def test_deleted_document_is_not_announced(session_factory, path, cause):
    store, index = InMemoryObjectStore(), InMemoryIndex()
    with session_factory() as s:
        doc = register(s, "documents/" + "88" * 32)
        other = register(s, "documents/" + "99" * 32)
        s.flush()
        gs = PostgresGrantStore(s)
        removed = gs.issue("ontvanger", ["EMAIL"], actor="t", document_id=doc.id)
        elsewhere = gs.issue("derde", ["EMAIL"], actor="t", document_id=other.id)
        s.commit()
        doc_id, removed_id, elsewhere_id = doc.id, removed.grant_id, elsewhere.grant_id
    with session_factory() as s:
        delete_document(s, doc_id, store, index, actor="t")
        s.commit()
    grant_id, key = {
        "unknown-grant": ("no-such-grant", "kontvanger"),
        "removed-grant": (removed_id, "kontvanger"),
        "other-caller": (elsewhere_id, "kderde"),
    }[cause]
    client = _client(session_factory, store=store)
    r = client.post(f"/documents/{doc_id}{path}", json={"grant_id": grant_id},
                    headers={"X-API-Key": key})
    assert r.status_code == 403
    assert r.json() == REFUSAL


# --- Shared world for 2.8 and 4.1: the eight causes of the uniform refusal -

def _eight_causes(session_factory):
    store, index = InMemoryObjectStore(), InMemoryIndex()
    with session_factory() as s:
        doc_a = register(s, "documents/" + "a1" * 32)
        doc_b = register(s, "documents/" + "b2" * 32)
        deleted = register(s, "documents/" + "c3" * 32)
        s.commit()
        doc_a_id, doc_b_id, deleted_id = doc_a.id, doc_b.id, deleted.id
    with session_factory() as s:
        copy = register(s, "documents/" + "a1" * 32)  # shares doc_a's key
        s.flush()
        supersede(s, copy.id, doc_a_id, actor="t")
        s.commit()
        copy_id = copy.id
    with session_factory() as s:
        delete_document(s, deleted_id, store, index, actor="t")
        s.commit()
    unknown_id = uuid4()
    with session_factory() as s:
        gs = PostgresGrantStore(s)
        revoked = gs.issue("derde", ["EMAIL"], actor="t", document_id=doc_a_id)
        gs.revoke(revoked.grant_id, "t")
        expired = gs.issue("derde", ["EMAIL"], actor="t", document_id=doc_a_id,
                           expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        other_doc = gs.issue("derde", ["EMAIL"], actor="t", document_id=doc_b_id)
        other_recipient = gs.issue("ontvanger", ["EMAIL"], actor="t",
                                   document_id=doc_a_id)
        # Unscoped + global, not document-scoped: `grants.document_id` has a
        # foreign key to `documents`, so a grant cannot point at an id that
        # was never registered. A grant that would cover ANY document is the
        # realistic way to present "his, otherwise live, grant" against one
        # that does not exist (task 2.7).
        own_unknown = gs.issue("derde", ["EMAIL"], actor="t", document_id=None)
        s.commit()
        requests = [
            ("unknown grant", "no-such-grant", doc_a_id),
            ("revoked", revoked.grant_id, doc_a_id),
            ("expired", expired.grant_id, doc_a_id),
            ("scoped elsewhere", other_doc.grant_id, doc_a_id),
            ("other recipient", other_recipient.grant_id, doc_a_id),
            ("unknown document", own_unknown.grant_id, unknown_id),
            ("superseded", other_doc.grant_id, copy_id),
            ("deleted", other_doc.grant_id, deleted_id),
        ]
    return store, requests


@pytest.mark.parametrize("path", ROUTES)
def test_all_causes_give_one_answer(legacy_copies, path):
    store, requests = _eight_causes(legacy_copies)
    client = _client(legacy_copies, store=store, allow_global_grants=True)
    for accept in ("application/json", "text/html"):
        answers = [
            client.post(f"/documents/{target}{path}", json={"grant_id": grant_id},
                       headers={"X-API-Key": "kderde", "accept": accept})
            for _, grant_id, target in requests
        ]
        assert [a.status_code for a in answers] == [403] * len(requests)
        if accept == "application/json":
            bodies = [a.json() for a in answers]
        else:
            bodies = [_scrub_ids(a.text) for a in answers]
        assert all(b == bodies[0] for b in bodies), bodies


# --- 3.2: a covered caller is told the document is deleted ------------------

@pytest.mark.parametrize("path", ROUTES)
@pytest.mark.parametrize("cover", ["global-flag", "admin-role"])
def test_covered_caller_is_told_document_is_deleted(session_factory, path, cover):
    store, index = InMemoryObjectStore(), InMemoryIndex()
    with session_factory() as s:
        doc = register(s, "documents/" + "d4" * 32)
        s.commit()
        doc_id = doc.id
    with session_factory() as s:
        delete_document(s, doc_id, store, index, actor="t")
        s.commit()
    with session_factory() as s:
        ensure_admin_role(s)
        kwargs = {"role": roles_mod.ADMIN} if cover == "admin-role" else {}
        grant = PostgresGrantStore(s).issue("ontvanger", ["EMAIL"], actor="t",
                                            document_id=None, **kwargs)
        s.commit()
        grant_id = grant.grant_id

    client = _client(session_factory, store=store,
                     allow_global_grants=(cover == "global-flag"))
    r = client.post(f"/documents/{doc_id}{path}", json={"grant_id": grant_id},
                    headers={"X-API-Key": "kontvanger"})
    assert r.status_code == 410
    with session_factory() as s:
        n = s.execute(select(func.count()).select_from(AuditRecord).where(
            AuditRecord.document_id == doc_id,
            AuditRecord.step == "deanonymize")).scalar_one()
    assert n == 0


# --- 3.4: a covered caller is told the document is not yet de-identified ---

def test_covered_caller_is_told_not_yet_de_identified(session_factory):
    with session_factory() as s:
        doc = register(s, "documents/" + "e5" * 32)
        grant = PostgresGrantStore(s).issue("ontvanger", ["EMAIL"], actor="t",
                                            document_id=doc.id)
        s.commit()
        doc_id, grant_id = doc.id, grant.grant_id
    client = _client(session_factory, store=InMemoryObjectStore())
    r = client.post(f"/documents/{doc_id}/reveal", json={"grant_id": grant_id},
                    headers={"X-API-Key": "kontvanger"})
    assert r.status_code == 409
    assert "not yet de-identified" in r.json()["detail"]


# --- 3.8: a covered caller without a required credential ------------------

@pytest.mark.parametrize("path", ROUTES)
def test_covered_caller_without_required_credential_hears_nothing(
        legacy_copies, path):
    session_factory = legacy_copies
    store, index = InMemoryObjectStore(), InMemoryIndex()
    with session_factory() as s:
        survivor = register(s, "documents/" + "f6" * 32)
        s.flush()
        copy = register(s, "documents/" + "f6" * 32)
        s.flush()
        supersede(s, copy.id, survivor.id, actor="t")
        deleted = register(s, "documents/" + "17" * 32)
        s.commit()
        copy_id, deleted_id = copy.id, deleted.id
    with session_factory() as s:
        delete_document(s, deleted_id, store, index, actor="t")
        s.commit()
    with session_factory() as s:
        gs = PostgresGrantStore(s)
        grant_on_copy = gs.issue("ontvanger", ["EMAIL"], actor="t", document_id=copy_id)
        grant_on_deleted = gs.issue("ontvanger", ["EMAIL"], actor="t",
                                    document_id=deleted_id)
        s.commit()
        copy_grant, deleted_grant = grant_on_copy.grant_id, grant_on_deleted.grant_id

    key = ec.generate_private_key(ec.SECP256R1())
    client = _client(session_factory, store=store, vc_public_key=key.public_key(),
                     vc_required=True)
    for grant_id, target in ((copy_grant, copy_id), (deleted_grant, deleted_id)):
        for headers in ({}, {"X-VC": "garbage"}):
            r = client.post(f"/documents/{target}{path}", json={"grant_id": grant_id},
                            headers={**headers, "X-API-Key": "kontvanger"})
            assert r.status_code == 403
            assert r.json()["detail"].startswith("vc rejected")


def test_vc_narrowing_still_lets_a_covered_caller_be_told_deleted(session_factory):
    """Sanity check for the gate ordering: a VALID credential does not block
    the 410 a covered caller is owed (only a rejected one would)."""
    store, index = InMemoryObjectStore(), InMemoryIndex()
    with session_factory() as s:
        doc = register(s, "documents/" + "18" * 32)
        s.commit()
        doc_id = doc.id
    with session_factory() as s:
        delete_document(s, doc_id, store, index, actor="t")
        s.commit()
    with session_factory() as s:
        # Unscoped (+ global), so the deletion -- which only clears grants
        # scoped to the document -- leaves it covering the document still.
        grant = PostgresGrantStore(s).issue("ontvanger", ["EMAIL"], actor="t",
                                            document_id=None)
        s.commit()
        grant_id = grant.grant_id
    key = ec.generate_private_key(ec.SECP256R1())
    vc = issue_sdjwt_vc(key, vct="t", issuer="i",
                        selective_claims={"authorized_types": ["EMAIL"]})
    client = _client(session_factory, store=store, vc_public_key=key.public_key(),
                     allow_global_grants=True)
    r = client.post(f"/documents/{doc_id}/reveal", json={"grant_id": grant_id},
                    headers={"X-API-Key": "kontvanger", "X-VC": vc.present()})
    assert r.status_code == 410


# --- 4.1: a refusal writes no audit record ----------------------------------

@pytest.mark.parametrize("path", ROUTES)
def test_a_refusal_writes_no_audit_record(legacy_copies, path):
    store, requests = _eight_causes(legacy_copies)
    client = _client(legacy_copies, store=store, allow_global_grants=True)
    for _, grant_id, target in requests:
        with legacy_copies() as s:
            before = (s.execute(select(func.count()).select_from(AuditRecord)).scalar_one(),
                     s.execute(select(func.count()).select_from(KeyLifecycleEvent)).scalar_one())
        r = client.post(f"/documents/{target}{path}", json={"grant_id": grant_id},
                        headers={"X-API-Key": "kderde"})
        assert r.status_code == 403
        with legacy_copies() as s:
            after = (s.execute(select(func.count()).select_from(AuditRecord)).scalar_one(),
                    s.execute(select(func.count()).select_from(KeyLifecycleEvent)).scalar_one())
            ok, bad = verify_chain(s)
        assert before == after
        assert ok is True and bad is None


# --- 4.2: a refusal logs nothing about its cause ----------------------------

@pytest.mark.parametrize("path", ROUTES)
def test_a_refusal_logs_nothing_about_its_cause(legacy_copies, caplog, path):
    session_factory = legacy_copies
    store, index = InMemoryObjectStore(), InMemoryIndex()
    with session_factory() as s:
        survivor = register(s, "documents/" + "28" * 32)
        s.flush()
        copy = register(s, "documents/" + "28" * 32)
        s.flush()
        supersede(s, copy.id, survivor.id, actor="t")
        deleted = register(s, "documents/" + "39" * 32)
        out_of_scope = register(s, "documents/" + "4a" * 32)
        granted_elsewhere = register(s, "documents/" + "5b" * 32)
        s.commit()
        copy_id, deleted_id = copy.id, deleted.id
        out_of_scope_id, elsewhere_id = out_of_scope.id, granted_elsewhere.id
    with session_factory() as s:
        delete_document(s, deleted_id, store, index, actor="t")
        s.commit()
    with session_factory() as s:
        grant = PostgresGrantStore(s).issue("derde", ["EMAIL"], actor="t",
                                            document_id=elsewhere_id)
        s.commit()
        grant_id = grant.grant_id

    unknown_id = uuid4()
    client = _client(session_factory, store=store)
    forbidden_words = ("unknown", "superseded", "deleted")
    per_case = []
    for target in (unknown_id, copy_id, deleted_id, out_of_scope_id):
        caplog.clear()
        with caplog.at_level(logging.DEBUG, logger="wordsworth"):
            r = client.post(f"/documents/{target}{path}", json={"grant_id": grant_id},
                            headers={"X-API-Key": "kderde"})
        assert r.status_code == 403
        messages = [_scrub_ids(rec.getMessage()) for rec in caplog.records]
        for msg in messages:
            lowered = msg.lower()
            assert not any(w in lowered for w in forbidden_words), msg
        per_case.append(messages)
    assert all(case == per_case[0] for case in per_case), per_case
