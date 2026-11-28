"""design.md "POST /v1/pseudonymise": tokens out, the registry filled, the
known_documents rules, the cap, Transit failure, and no clear value ever
reaching a response or a log line."""
from __future__ import annotations

import logging
import uuid

import pytest
from fastapi.testclient import TestClient

from wordsworth.keys import DurableKeyProvider
from wordsworth.keyservice import serve
from wordsworth.keyservice.models import DocumentToken, KnownDocument
from wordsworth.keyservice.stores_pii import PostgresKeyVaultStore, PostgresMappingStore
from wordsworth.pseudonymizer import Pseudonymizer
from wordsworth.transit import FakeTransit


class _RefusingTransit:
    """Simulates OpenBao unreachable/sealed -- the same style as
    tests/test_document_keys.py and tests/test_ingest_fail_closed.py."""

    def wrap(self, plaintext: bytes) -> bytes:
        raise RuntimeError("key service down")

    def unwrap(self, ciphertext: bytes) -> bytes:
        raise RuntimeError("key service down")


def _app(keyservice_database_url, monkeypatch, tokens=None, transit_for=None):
    monkeypatch.setenv("KEYSERVICE_DATABASE_URL", keyservice_database_url)
    monkeypatch.delenv("WORDSWORTH_DATABASE_URL", raising=False)
    return serve.create_app(
        service_tokens=tokens if tokens is not None else {"tok": "ingest"},
        transit_for=transit_for if transit_for is not None else (lambda kek: FakeTransit()))


def _client(app):
    return TestClient(app, headers={"Authorization": "Bearer tok"})


def test_tokens_only_no_value_in_the_response(keyservice_session_factory,
                                              keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch)
    doc_id = str(uuid.uuid4())
    with _client(app) as client:
        resp = client.post("/v1/pseudonymise", json={
            "document_id": doc_id, "domain": "example",
            "items": [{"type": "PERSON", "value": "Jan Jansen"}],
        })
    assert resp.status_code == 200
    body = resp.json()
    assert body["document_id"] == doc_id
    assert len(body["tokens"]) == 1
    assert body["tokens"][0].startswith("[PERSON:")
    assert "Jan Jansen" not in resp.text


def test_token_matches_wordsworths_own_pseudonymizer_formula(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch)
    doc_id = str(uuid.uuid4())
    with _client(app) as client:
        resp = client.post("/v1/pseudonymise", json={
            "document_id": doc_id, "domain": "example",
            "items": [{"type": "PERSON", "value": "Jan Jansen"}],
        })
    token = resp.json()["tokens"][0]

    # Same KEK material (FakeTransit's default KEK is a fixed class
    # constant), same stores, same unmodified Pseudonymizer -- the service
    # mints no token of its own shape, it only calls wordsworth's function.
    with keyservice_session_factory() as session:
        provider = DurableKeyProvider(PostgresKeyVaultStore(session), FakeTransit())
        pseudonymizer = Pseudonymizer(
            provider, PostgresMappingStore(session), domain="example")
        again = pseudonymizer.pseudonym("PERSON", "Jan Jansen")
    assert again == token


def test_token_is_registered_only_for_its_own_document(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch)
    doc_a, doc_b = str(uuid.uuid4()), str(uuid.uuid4())
    with _client(app) as client:
        resp = client.post("/v1/pseudonymise", json={
            "document_id": doc_a, "domain": "example",
            "items": [{"type": "PERSON", "value": "Jan Jansen"}],
        })
    token = resp.json()["tokens"][0]

    with keyservice_session_factory() as session:
        rows_a = session.get(DocumentToken, (uuid.UUID(doc_a), token))
        rows_b = session.get(DocumentToken, (uuid.UUID(doc_b), token))
    assert rows_a is not None
    assert rows_a.source == "minted"
    assert rows_b is None


def test_repseudonymising_adds_and_never_removes_tokens(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch)
    doc_id = str(uuid.uuid4())
    with _client(app) as client:
        first = client.post("/v1/pseudonymise", json={
            "document_id": doc_id, "domain": "example",
            "items": [{"type": "PERSON", "value": "Jan Jansen"}],
        }).json()["tokens"]
        second = client.post("/v1/pseudonymise", json={
            "document_id": doc_id, "domain": "example",
            "items": [{"type": "EMAIL", "value": "jan@example.com"}],
        }).json()["tokens"]

    with keyservice_session_factory() as session:
        tokens = {t.token for t in session.query(DocumentToken)
                  .filter_by(document_id=uuid.UUID(doc_id)).all()}
    assert set(first) <= tokens
    assert set(second) <= tokens


def test_empty_batch_registers_the_document(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch)
    doc_id = str(uuid.uuid4())
    with _client(app) as client:
        resp = client.post("/v1/pseudonymise", json={
            "document_id": doc_id, "domain": "example", "items": [],
        })
    assert resp.status_code == 200
    assert resp.json()["tokens"] == []

    with keyservice_session_factory() as session:
        row = session.get(KnownDocument, uuid.UUID(doc_id))
    assert row is not None
    assert row.domain == "example"


@pytest.mark.parametrize("label", ["PERSON", "phone_number", "SOME_UNKNOWN_TYPE"])
def test_a_label_matching_the_token_alphabet_is_accepted(
        keyservice_session_factory, keyservice_database_url, monkeypatch, label):
    # No closed list: even a label wordsworth's pii_categories does not know
    # is accepted (design.md "Type labels").
    app = _app(keyservice_database_url, monkeypatch)
    with _client(app) as client:
        resp = client.post("/v1/pseudonymise", json={
            "document_id": str(uuid.uuid4()), "domain": "example",
            "items": [{"type": label, "value": "x"}],
        })
    assert resp.status_code == 200


@pytest.mark.parametrize("label", ["bad label", "bad/label", ""])
def test_a_label_outside_the_token_alphabet_is_refused(
        keyservice_session_factory, keyservice_database_url, monkeypatch, label):
    app = _app(keyservice_database_url, monkeypatch)
    with _client(app) as client:
        resp = client.post("/v1/pseudonymise", json={
            "document_id": str(uuid.uuid4()), "domain": "example",
            "items": [{"type": label, "value": "x"}],
        })
    assert resp.status_code == 422
    assert "x" not in resp.text


@pytest.mark.parametrize("domain", ["", "has/slash"])
def test_a_domain_with_slash_or_empty_is_refused(
        keyservice_session_factory, keyservice_database_url, monkeypatch, domain):
    app = _app(keyservice_database_url, monkeypatch)
    with _client(app) as client:
        resp = client.post("/v1/pseudonymise", json={
            "document_id": str(uuid.uuid4()), "domain": domain, "items": [],
        })
    assert resp.status_code == 422


def test_a_different_domain_later_is_409_and_changes_nothing(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch)
    doc_id = str(uuid.uuid4())
    with _client(app) as client:
        client.post("/v1/pseudonymise", json={
            "document_id": doc_id, "domain": "example", "items": [],
        })
        resp = client.post("/v1/pseudonymise", json={
            "document_id": doc_id, "domain": "other",
            "items": [{"type": "PERSON", "value": "Jan Jansen"}],
        })
    assert resp.status_code == 409

    with keyservice_session_factory() as session:
        row = session.get(KnownDocument, uuid.UUID(doc_id))
        tokens = session.query(DocumentToken).filter_by(
            document_id=uuid.UUID(doc_id)).all()
    assert row.domain == "example"
    assert tokens == []


def test_a_tombstoned_document_is_410(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    from datetime import datetime, timezone

    doc_id = uuid.uuid4()
    with keyservice_session_factory() as session:
        session.add(KnownDocument(id=doc_id, domain="example",
                                  registered_at=datetime.now(timezone.utc),
                                  deleted_at=datetime.now(timezone.utc)))
        session.commit()

    app = _app(keyservice_database_url, monkeypatch)
    with _client(app) as client:
        resp = client.post("/v1/pseudonymise", json={
            "document_id": str(doc_id), "domain": "example",
            "items": [{"type": "PERSON", "value": "Jan Jansen"}],
        })
    assert resp.status_code == 410


def test_a_batch_at_the_cap_is_accepted(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    monkeypatch.setenv("KEYSERVICE_PSEUDONYMISE_MAX_ITEMS", "2")
    app = _app(keyservice_database_url, monkeypatch)
    with _client(app) as client:
        resp = client.post("/v1/pseudonymise", json={
            "document_id": str(uuid.uuid4()), "domain": "example",
            "items": [{"type": "PERSON", "value": "a"},
                     {"type": "PERSON", "value": "b"}],
        })
    assert resp.status_code == 200
    assert len(resp.json()["tokens"]) == 2


def test_a_batch_over_the_cap_is_refused_and_registers_nothing(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    monkeypatch.setenv("KEYSERVICE_PSEUDONYMISE_MAX_ITEMS", "2")
    app = _app(keyservice_database_url, monkeypatch)
    doc_id = str(uuid.uuid4())
    with _client(app) as client:
        resp = client.post("/v1/pseudonymise", json={
            "document_id": doc_id, "domain": "example",
            "items": [{"type": "PERSON", "value": "a"},
                     {"type": "PERSON", "value": "b"},
                     {"type": "PERSON", "value": "c"}],
        })
    assert resp.status_code == 422

    with keyservice_session_factory() as session:
        assert session.get(KnownDocument, uuid.UUID(doc_id)) is None


def test_transit_down_is_503_and_commits_nothing(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch,
              transit_for=lambda kek: _RefusingTransit())
    doc_id = str(uuid.uuid4())
    with _client(app) as client:
        resp = client.post("/v1/pseudonymise", json={
            "document_id": doc_id, "domain": "example",
            "items": [{"type": "PERSON", "value": "Jan Jansen"}],
        })
    assert resp.status_code == 503
    assert resp.json()["detail"] == "key service unavailable"

    with keyservice_session_factory() as session:
        assert session.get(KnownDocument, uuid.UUID(doc_id)) is None
        assert session.query(DocumentToken).filter_by(
            document_id=uuid.UUID(doc_id)).first() is None
        from wordsworth.keyservice.models_access import AccessAudit
        assert session.query(AccessAudit).count() == 0


def test_one_access_audit_record_per_call_with_counts_and_no_value(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch)
    doc_id = str(uuid.uuid4())
    with _client(app) as client:
        client.post("/v1/pseudonymise", json={
            "document_id": doc_id, "domain": "example",
            "items": [{"type": "PERSON", "value": "Jan Jansen"},
                     {"type": "PERSON", "value": "Piet Pietersen"}],
        })

    from wordsworth.keyservice.models_access import AccessAudit
    with keyservice_session_factory() as session:
        records = session.query(AccessAudit).all()
    assert len(records) == 1
    record = records[0]
    assert record.event == "pseudonymise"
    assert record.service_caller == "ingest"
    assert record.payload["counts"] == {"PERSON": 2}
    assert record.payload["new_registry_rows"] == 2
    dump = str(record.payload)
    assert "Jan Jansen" not in dump
    assert "Piet Pietersen" not in dump


def test_no_clear_value_in_any_log_line(
        keyservice_session_factory, keyservice_database_url, monkeypatch, caplog):
    app = _app(keyservice_database_url, monkeypatch)
    sentinel = "SENTINEL-VALUE-f3b1c9"
    with caplog.at_level(logging.DEBUG):
        with _client(app) as client:
            resp = client.post("/v1/pseudonymise", json={
                "document_id": str(uuid.uuid4()), "domain": "example",
                "items": [{"type": "PERSON", "value": sentinel}],
            })
    assert resp.status_code == 200
    assert sentinel not in caplog.text
    assert sentinel not in resp.text
