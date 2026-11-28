"""design.md "Locks": a document deletion, an originals deletion and a seal
run against each other without a deadlock -- the originals deletion never
takes the registry lock (4781), so no cycle through it is possible. And the
#465 twin: a pseudonymise of a shared value for another document running
against a deletion decides "no other document holds this token" under the
same registry lock a deletion takes, so the mapping survives whichever
commits first (``docs/reference/lock-order.md``, "pii_mappings is written
under the chain lock" -- the key service's equivalent is the registry lock)."""
from __future__ import annotations

import threading
import uuid

from fastapi.testclient import TestClient
from race_setup import run, wait_for_a_lock_waiter

from wordsworth.keyservice import api_documents, api_pseudonymise, known, serve
from wordsworth.keyservice.models import DocumentToken, PiiMapping
from wordsworth.transit import FakeTransit


def _app(keyservice_database_url, monkeypatch, tokens=None):
    monkeypatch.setenv("KEYSERVICE_DATABASE_URL", keyservice_database_url)
    monkeypatch.delenv("WORDSWORTH_DATABASE_URL", raising=False)
    return serve.create_app(
        service_tokens=tokens if tokens is not None else {"tok": "ingest"},
        transit_for=lambda kek: FakeTransit())


def _client(app):
    return TestClient(app, headers={"Authorization": "Bearer tok"})


def _seal(client, document_id, domain="acme", object_key="documents/a",
         body=b"plaintext bytes"):
    return client.post(f"/v1/originals/{document_id}/seal",
                       params={"domain": domain, "object_key": object_key},
                       content=body)


def _pseudonymise(client, document_id, domain="acme", items=()):
    return client.post("/v1/pseudonymise", json={
        "document_id": str(document_id), "domain": domain, "items": list(items)})


def test_a_document_deletion_an_originals_deletion_and_a_seal_do_not_deadlock(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch)
    doc_id = str(uuid.uuid4())
    with _client(app) as client:
        _seal(client, doc_id, object_key="documents/a")

    errors, paused, resume = {}, threading.Event(), threading.Event()
    real_append_lifecycle = api_documents.lifecycle.append_lifecycle

    def paused_append_lifecycle(*args, **kwargs):
        # Past the registry lock and the document_keys row lock
        # (``delete_document``'s order), before the lifecycle/audit records.
        paused.set()
        assert resume.wait(30), "never resumed"
        return real_append_lifecycle(*args, **kwargs)
    monkeypatch.setattr(api_documents.lifecycle, "append_lifecycle",
                        paused_append_lifecycle)

    with _client(app) as client:
        def deleting_document():
            resp = client.delete(f"/v1/documents/{doc_id}")
            assert resp.status_code == 200

        def deleting_originals():
            client.delete(f"/v1/originals/{doc_id}")

        def sealing():
            _seal(client, doc_id, object_key="documents/a", body=b"second body")

        dele = run(errors, "delete-document", deleting_document)
        assert paused.wait(10), "delete_document never reached the pause"
        orig = run(errors, "delete-originals", deleting_originals)
        seal_thread = run(errors, "seal", sealing)
        try:
            wait_for_a_lock_waiter(keyservice_session_factory)
        finally:
            resume.set()
            dele.join(30)
            orig.join(30)
            seal_thread.join(30)

    assert not errors, errors


def _pause_before_lock_registry(monkeypatch, paused, resume):
    """Pauses only the FIRST caller (the pseudonymise thread) -- ``known``
    is shared by every writer that takes the registry lock, including the
    deletion this test runs next, which must not pause a second time."""
    real = known.lock_registry
    state = {"paused_once": False}

    def paused_lock_registry(session):
        if not state["paused_once"]:
            state["paused_once"] = True
            paused.set()
            assert resume.wait(30), "never resumed"
        return real(session)
    monkeypatch.setattr(known, "lock_registry", paused_lock_registry)


def _pause_in_register_tokens(monkeypatch, paused, resume):
    real = api_pseudonymise._register_tokens

    def paused_register(session, document_id, tokens):
        # Past the registry lock and the pseudonymizer loop, before the
        # tokens are registered and the transaction commits.
        paused.set()
        assert resume.wait(30), "never resumed"
        return real(session, document_id, tokens)
    monkeypatch.setattr(api_pseudonymise, "_register_tokens", paused_register)


def test_a_shared_value_survives_when_the_pseudonymise_commits_first(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch)
    doc_a, doc_b = str(uuid.uuid4()), str(uuid.uuid4())
    with _client(app) as client:
        token = _pseudonymise(
            client, doc_a, items=[{"type": "PERSON", "value": "Jan Jansen"}]
        ).json()["tokens"][0]

    errors, paused, resume = {}, threading.Event(), threading.Event()
    _pause_in_register_tokens(monkeypatch, paused, resume)

    with _client(app) as client:
        def pseudonymising_b():
            resp = _pseudonymise(
                client, doc_b, items=[{"type": "PERSON", "value": "Jan Jansen"}])
            assert resp.status_code == 200

        pseudo = run(errors, "pseudonymise-b", pseudonymising_b)
        assert paused.wait(10), "pseudonymise never reached the pause"

        def deleting_a():
            resp = client.delete(f"/v1/documents/{doc_a}")
            assert resp.status_code == 200

        dele = run(errors, "delete-a", deleting_a)
        try:
            wait_for_a_lock_waiter(keyservice_session_factory)
        finally:
            resume.set()
            pseudo.join(30)
            dele.join(30)

    assert not errors, errors
    with keyservice_session_factory() as session:
        assert session.get(PiiMapping, token) is not None, \
            "the mapping B relies on was deleted with A"
        assert session.get(DocumentToken, (uuid.UUID(doc_b), token)) is not None
        assert session.get(DocumentToken, (uuid.UUID(doc_a), token)) is None


def test_a_mapping_deleted_before_the_link_is_put_back(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch)
    doc_a, doc_b = str(uuid.uuid4()), str(uuid.uuid4())
    with _client(app) as client:
        token = _pseudonymise(
            client, doc_a, items=[{"type": "PERSON", "value": "Piet Pietersen"}]
        ).json()["tokens"][0]

    errors, paused, resume = {}, threading.Event(), threading.Event()
    _pause_before_lock_registry(monkeypatch, paused, resume)

    with _client(app) as client:
        def pseudonymising_b():
            resp = _pseudonymise(
                client, doc_b, items=[{"type": "PERSON", "value": "Piet Pietersen"}])
            assert resp.status_code == 200

        pseudo = run(errors, "pseudonymise-b", pseudonymising_b)
        assert paused.wait(10), "pseudonymise never reached the pause"

        # A's deletion runs to completion while B's pseudonymise has not yet
        # taken the registry lock: A was the token's only holder, so the
        # mapping is removed as orphaned.
        resp = client.delete(f"/v1/documents/{doc_a}")
        assert resp.status_code == 200
        with keyservice_session_factory() as session:
            assert session.get(PiiMapping, token) is None

        resume.set()
        pseudo.join(30)

    assert not errors, errors
    with keyservice_session_factory() as session:
        assert session.get(PiiMapping, token) is not None, \
            "B never stored the mapping again after A's deletion removed it"
        assert session.get(DocumentToken, (uuid.UUID(doc_b), token)) is not None
