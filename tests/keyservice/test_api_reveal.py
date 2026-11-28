"""``POST /v1/reveal/decide`` and ``POST /v1/reveal`` (design.md "Order
inside the service", "Requests", "Status codes, key service"). Assertions
are signed with a real RSA key, not a stub that says "valid" -- the
pattern of ``tests/test_access_identity.py``."""
from __future__ import annotations

import base64
import json
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from fastapi.testclient import TestClient
from sqlalchemy import event

from wordsworth import access_identity
from wordsworth.keys import DurableKeyProvider
from wordsworth.keyservice import serve
from wordsworth.keyservice.api_documents import delete_document
from wordsworth.keyservice.models import DocumentToken, KnownDocument
from wordsworth.keyservice.models_access import AccessAudit, GrantRecord, Role
from wordsworth.keyservice.stores_pii import PostgresKeyVaultStore, PostgresMappingStore
from wordsworth.pseudonymizer import Pseudonymizer
from wordsworth.transit import FakeTransit

ISSUER = "https://iam.westerweel.work/realms/westerweel"
AUDIENCE = "wordsworth-keyservice"
JWKS_URL = f"{ISSUER}/certs"
#: The route verifies against the real wall clock (``time.time()``), never
#: an injected one -- so assertions in these tests must be timed against it.
NOW = time.time()
REFUSAL = {"detail": "grant not applicable"}
FORBIDDEN_TABLES = ("known_documents", "document_tokens", "pii_mappings", "key_vault")


# --- signing + app wiring ----------------------------------------------------

def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _jwks(key, kid="k1"):
    n = key.public_key().public_numbers()
    return {"keys": [{"kty": "RSA", "kid": kid,
                      "n": _b64(n.n.to_bytes((n.n.bit_length() + 7) // 8, "big")),
                      "e": _b64(n.e.to_bytes((n.e.bit_length() + 7) // 8, "big"))}]}


def _assertion(key, kid="k1", alg="RS256", **claims):
    body = {"aud": [AUDIENCE], "iss": ISSUER, "exp": NOW + 3600,
           "email": "ontvanger@example.com", "email_verified": True}
    body.update(claims)
    head = _b64(json.dumps({"alg": alg, "kid": kid}).encode())
    payload = _b64(json.dumps(body).encode())
    sig = key.sign(f"{head}.{payload}".encode(), padding.PKCS1v15(), hashes.SHA256())
    return f"{head}.{payload}.{_b64(sig)}"


@pytest.fixture
def key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


class _RefusingTransit:
    def wrap(self, plaintext: bytes) -> bytes:
        raise RuntimeError("key service down")

    def unwrap(self, ciphertext: bytes) -> bytes:
        raise RuntimeError("key service down")


def _app(keyservice_database_url, monkeypatch, key, *, configured=True,
         transit_for=None, **env):
    monkeypatch.setenv("KEYSERVICE_DATABASE_URL", keyservice_database_url)
    monkeypatch.delenv("WORDSWORTH_DATABASE_URL", raising=False)
    if configured:
        monkeypatch.setenv("KEYSERVICE_OIDC_ISSUER", ISSUER)
        monkeypatch.setenv("KEYSERVICE_OIDC_AUDIENCE", AUDIENCE)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    app = serve.create_app(
        service_tokens={"tok": "wordsworth"},
        transit_for=transit_for or (lambda kek: FakeTransit()))
    if configured:
        verifier = access_identity.Verifier.oidc(ISSUER, AUDIENCE, jwks_url=JWKS_URL)
        identity = access_identity.Identity(verifier)
        identity._keys, identity._at = (
            access_identity.public_keys(verifier, fetch=lambda url: _jwks(key)), NOW)
        app.state.identity = identity
    return app


def _client(app):
    return TestClient(app, headers={"Authorization": "Bearer tok"})


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


def _forbidden_hits(statements, tables=FORBIDDEN_TABLES):
    import re
    return [(t, s) for s in statements for t in tables if re.search(rf"\b{t}\b", s)]


# --- seeding helpers -----------------------------------------------------

def _seed_document(session, document_id, domain="_global"):
    session.add(KnownDocument(id=document_id, domain=domain,
                              registered_at=datetime.now(timezone.utc)))
    session.flush()


def _seed_token(session, document_id, label, value, domain="_global"):
    provider = DurableKeyProvider(PostgresKeyVaultStore(session), FakeTransit())
    pseudonymizer = Pseudonymizer(provider, PostgresMappingStore(session), domain=domain)
    token = pseudonymizer.pseudonym(label, value)
    session.add(DocumentToken(document_id=document_id, token=token, source="minted",
                              created_at=datetime.now(timezone.utc)))
    session.flush()
    return token


def _seed_grant(session, grant_id, recipient, allowed_types, *, document_id=None,
                domain=None, status="active", expires_at=None, role=None):
    session.add(GrantRecord(
        grant_id=grant_id, recipient=recipient, allowed_types=allowed_types,
        document_id=document_id, status=status, created_at=datetime.now(timezone.utc),
        revoked_at=None, expires_at=expires_at, actor="t", domain=domain, role=role))
    session.flush()


def _seed_admin_role(session):
    from wordsworth.keyservice.roles import ADMIN
    session.add(Role(name=ADMIN, allowed_types=["PERSON", "EMAIL"], active=True,
                     created_by="t"))
    session.flush()


ASSERTION_CAUSES = {
    "missing": lambda key: "",
    "forged": lambda key: _assertion(rsa.generate_private_key(public_exponent=65537, key_size=2048)),
    "expired": lambda key: _assertion(key, exp=NOW - 1),
    "not_yet_valid": lambda key: _assertion(key, nbf=NOW + 3600),
    "wrong_issuer": lambda key: _assertion(key, iss="https://kwaadaardig.example"),
    "foreign_audience": lambda key: _assertion(key, aud=["een-andere-app"]),
    "missing_email": lambda key: _assertion(key, email=""),
    "unverified_email": lambda key: _assertion(key, email_verified=False),
    "cloudflare_style": lambda key: _assertion(key, iss="https://x.cloudflareaccess.com",
                                               aud=["x"]),
}


@pytest.mark.parametrize("path", ["/v1/reveal/decide", "/v1/reveal"])
@pytest.mark.parametrize("cause", list(ASSERTION_CAUSES))
def test_every_assertion_failure_gives_the_same_401(
        keyservice_session_factory, keyservice_database_url, monkeypatch, key, path, cause):
    engine = keyservice_session_factory.kw["bind"]
    app = _app(keyservice_database_url, monkeypatch, key)
    body = {"document_id": str(uuid.uuid4()), "grant_id": "g",
           "assertion": ASSERTION_CAUSES[cause](key)}
    if path == "/v1/reveal":
        body.update(tokens=[], view="text")
    with _client(app) as client:
        resp, statements = _statements_during(engine, lambda: client.post(path, json=body))
    assert resp.status_code == 401
    assert resp.json() == {"detail": "assertion not accepted"}
    # An assertion failure reads nothing at all -- not even the grant.
    assert _forbidden_hits(statements, FORBIDDEN_TABLES + ("grants",)) == []


@pytest.mark.parametrize("path", ["/v1/reveal/decide", "/v1/reveal"])
def test_without_oidc_settings_both_routes_answer_503(
        keyservice_session_factory, keyservice_database_url, monkeypatch, key, path):
    app = _app(keyservice_database_url, monkeypatch, key, configured=False)
    body = {"document_id": str(uuid.uuid4()), "grant_id": "g", "assertion": "x"}
    if path == "/v1/reveal":
        body.update(tokens=[], view="text")
    with _client(app) as client:
        resp = client.post(path, json=body)
    assert resp.status_code == 503
    assert resp.json() == {"detail": "reveal not configured"}


# --- the uniform refusal, grant-side causes -------------------------------

CAUSES = ["unknown_grant", "revoked", "expired", "other_document", "other_recipient"]


def _grant_causes(session, doc_id, other_id):
    grants = {}
    grants["unknown_grant"] = "no-such-grant"
    _seed_grant(session, "revoked", "ontvanger@example.com", ["PERSON"],
               document_id=doc_id, status="revoked")
    grants["revoked"] = "revoked"
    _seed_grant(session, "expired", "ontvanger@example.com", ["PERSON"],
               document_id=doc_id,
               expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    grants["expired"] = "expired"
    _seed_grant(session, "other_document", "ontvanger@example.com", ["PERSON"],
               document_id=other_id)
    grants["other_document"] = "other_document"
    _seed_grant(session, "other_recipient", "iemand.anders@example.com", ["PERSON"],
               document_id=doc_id)
    grants["other_recipient"] = "other_recipient"
    return grants


@pytest.mark.parametrize("path", ["/v1/reveal/decide", "/v1/reveal"])
@pytest.mark.parametrize("cause", CAUSES)
def test_an_uncovered_grant_reads_nothing_about_the_document_and_writes_no_record(
        keyservice_session_factory, keyservice_database_url, monkeypatch, key, path, cause):
    engine = keyservice_session_factory.kw["bind"]
    doc_id, other_id = uuid.uuid4(), uuid.uuid4()
    with keyservice_session_factory() as s:
        grants = _grant_causes(s, doc_id, other_id)
        s.commit()

    app = _app(keyservice_database_url, monkeypatch, key)
    body = {"document_id": str(doc_id), "grant_id": grants[cause],
           "assertion": _assertion(key)}
    if path == "/v1/reveal":
        body.update(tokens=[], view="text")
    with _client(app) as client:
        resp, statements = _statements_during(engine, lambda: client.post(path, json=body))
    assert resp.status_code == 403
    assert resp.json() == REFUSAL
    assert _forbidden_hits(statements) == []

    with keyservice_session_factory() as s:
        assert s.query(AccessAudit).count() == 0


@pytest.mark.parametrize("path", ["/v1/reveal/decide", "/v1/reveal"])
def test_unknown_document_and_tombstoned_outside_scope_give_the_same_answer(
        keyservice_session_factory, keyservice_database_url, monkeypatch, key, path):
    doc_id = uuid.uuid4()
    unknown_id = uuid.uuid4()
    with keyservice_session_factory() as s:
        _seed_document(s, doc_id)
        tombstoned = uuid.uuid4()
        s.add(KnownDocument(id=tombstoned, domain="_global",
                            registered_at=datetime.now(timezone.utc),
                            deleted_at=datetime.now(timezone.utc)))
        _seed_grant(s, "g-unknown", "ontvanger@example.com", ["PERSON"],
                   document_id=unknown_id)
        _seed_grant(s, "g-scoped", "ontvanger@example.com", ["PERSON"],
                   document_id=doc_id)
        s.commit()

    app = _app(keyservice_database_url, monkeypatch, key)
    with _client(app) as client:
        answers = []
        for grant_id, target in (("g-unknown", unknown_id), ("g-scoped", tombstoned)):
            body = {"document_id": str(target), "grant_id": grant_id,
                   "assertion": _assertion(key)}
            if path == "/v1/reveal":
                body.update(tokens=[], view="text")
            answers.append(client.post(path, json=body))
    assert [a.status_code for a in answers] == [403, 403]
    assert answers[0].json() == answers[1].json() == REFUSAL


# --- covered callers: tombstoned (survives via global/role), VC rejection --

@pytest.mark.parametrize("path", ["/v1/reveal/decide", "/v1/reveal"])
@pytest.mark.parametrize("cover", ["global_flag", "admin_role"])
def test_a_tombstoned_document_gives_410_to_a_grant_that_survived_the_deletion(
        keyservice_session_factory, keyservice_database_url, monkeypatch, key, path, cover):
    doc_id = uuid.uuid4()
    with keyservice_session_factory() as s:
        _seed_document(s, doc_id)
        s.commit()
    with keyservice_session_factory() as s:
        delete_document(s, doc_id, actor="wordsworth")
        s.commit()
    with keyservice_session_factory() as s:
        if cover == "admin_role":
            _seed_admin_role(s)
            from wordsworth.keyservice.roles import ADMIN
            _seed_grant(s, "g", "ontvanger@example.com", [], document_id=None, role=ADMIN)
        else:
            _seed_grant(s, "g", "ontvanger@example.com", ["PERSON"], document_id=None)
        s.commit()

    env = {"KEYSERVICE_ALLOW_GLOBAL_GRANTS": "true"} if cover == "global_flag" else {}
    app = _app(keyservice_database_url, monkeypatch, key, **env)
    body = {"document_id": str(doc_id), "grant_id": "g", "assertion": _assertion(key)}
    if path == "/v1/reveal":
        body.update(tokens=[], view="text")
    with _client(app) as client:
        resp = client.post(path, json=body)
    assert resp.status_code == 410
    assert resp.json() == {"detail": "document deleted"}


@pytest.mark.parametrize("path", ["/v1/reveal/decide", "/v1/reveal"])
def test_a_rejected_vc_is_403_and_never_410(
        keyservice_session_factory, keyservice_database_url, monkeypatch, key, path):
    doc_id = uuid.uuid4()
    with keyservice_session_factory() as s:
        _seed_document(s, doc_id)
        s.commit()
    with keyservice_session_factory() as s:
        delete_document(s, doc_id, actor="wordsworth")
        _seed_grant(s, "g", "ontvanger@example.com", ["PERSON"], document_id=None)
        s.commit()

    vc_key = ec.generate_private_key(ec.SECP256R1())
    app = _app(keyservice_database_url, monkeypatch, key,
              KEYSERVICE_ALLOW_GLOBAL_GRANTS="true")
    # Wire the VC public key directly (same shape as wordsworth's own composition root).
    import wordsworth.keyservice.api_reveal as api_reveal
    monkeypatch.setattr(api_reveal, "_vc_public_key", lambda: vc_key.public_key())
    body = {"document_id": str(doc_id), "grant_id": "g", "assertion": _assertion(key),
           "vc": "garbage"}
    if path == "/v1/reveal":
        body.update(tokens=[], view="text")
    with _client(app) as client:
        resp = client.post(path, json=body)
    assert resp.status_code == 403
    assert resp.json()["detail"].startswith("vc rejected")


def test_a_grant_on_a_deleted_document_gives_403_not_410(
        keyservice_session_factory, keyservice_database_url, monkeypatch, key):
    doc_id = uuid.uuid4()
    with keyservice_session_factory() as s:
        _seed_document(s, doc_id)
        _seed_grant(s, "g", "ontvanger@example.com", ["PERSON"], document_id=doc_id)
        s.commit()
    with keyservice_session_factory() as s:
        delete_document(s, doc_id, actor="wordsworth")  # removes the scoped grant
        s.commit()

    app = _app(keyservice_database_url, monkeypatch, key)
    body = {"document_id": str(doc_id), "grant_id": "g", "assertion": _assertion(key),
           "tokens": [], "view": "text"}
    with _client(app) as client:
        decide_resp = client.post("/v1/reveal/decide", json=body)
        reveal_resp = client.post("/v1/reveal", json=body)
    assert decide_resp.status_code == 403
    assert reveal_resp.status_code == 403
    assert decide_resp.json() == reveal_resp.json() == REFUSAL


@pytest.mark.parametrize("path", ["/v1/reveal/decide", "/v1/reveal"])
def test_a_document_never_seen_gives_the_uniform_403_even_to_a_naming_grant(
        keyservice_session_factory, keyservice_database_url, monkeypatch, key, path):
    unseen_id = uuid.uuid4()
    with keyservice_session_factory() as s:
        _seed_grant(s, "g", "ontvanger@example.com", ["PERSON"], document_id=unseen_id)
        s.commit()
    app = _app(keyservice_database_url, monkeypatch, key)
    body = {"document_id": str(unseen_id), "grant_id": "g", "assertion": _assertion(key)}
    if path == "/v1/reveal":
        body.update(tokens=[], view="text")
    with _client(app) as client:
        resp = client.post(path, json=body)
    assert resp.status_code == 403
    assert resp.json() == REFUSAL


@pytest.mark.parametrize("path", ["/v1/reveal/decide", "/v1/reveal"])
def test_a_grant_bound_to_another_domain_is_refused(
        keyservice_session_factory, keyservice_database_url, monkeypatch, key, path):
    doc_id = uuid.uuid4()
    with keyservice_session_factory() as s:
        _seed_document(s, doc_id, domain="afdeling-a")
        _seed_grant(s, "g", "ontvanger@example.com", ["PERSON"], document_id=doc_id,
                   domain="afdeling-b")
        s.commit()
    app = _app(keyservice_database_url, monkeypatch, key)
    body = {"document_id": str(doc_id), "grant_id": "g", "assertion": _assertion(key)}
    if path == "/v1/reveal":
        body.update(tokens=[], view="text")
    with _client(app) as client:
        resp = client.post(path, json=body)
    assert resp.status_code == 403
    assert resp.json() == REFUSAL


# --- the token limit --------------------------------------------------------

def test_more_tokens_than_the_limit_gives_413_and_decrypts_nothing(
        keyservice_session_factory, keyservice_database_url, monkeypatch, key):
    doc_id = uuid.uuid4()
    with keyservice_session_factory() as s:
        _seed_document(s, doc_id)
        _seed_grant(s, "g", "ontvanger@example.com", ["PERSON"], document_id=doc_id)
        s.commit()
    app = _app(keyservice_database_url, monkeypatch, key,
              KEYSERVICE_REVEAL_MAX_TOKENS="2")
    body = {"document_id": str(doc_id), "grant_id": "g", "assertion": _assertion(key),
           "tokens": ["[PERSON:aaaaaaaa]", "[PERSON:bbbbbbbb]", "[PERSON:cccccccc]"],
           "view": "text"}
    with _client(app) as client:
        resp = client.post("/v1/reveal", json=body)
    assert resp.status_code == 413
    assert resp.json() == {"detail": "too many tokens (limit 2)"}
    with keyservice_session_factory() as s:
        assert s.query(AccessAudit).count() == 0


# --- reveal: only this document's registered, authorised tokens ------------

def test_reveal_only_resolves_tokens_registered_for_this_document(
        keyservice_session_factory, keyservice_database_url, monkeypatch, key):
    doc_a, doc_b = uuid.uuid4(), uuid.uuid4()
    with keyservice_session_factory() as s:
        _seed_document(s, doc_a)
        _seed_document(s, doc_b)
        token_a = _seed_token(s, doc_a, "PERSON", "Jan Jansen")
        token_b = _seed_token(s, doc_b, "PERSON", "Piet Pietersen")
        _seed_grant(s, "g", "ontvanger@example.com", ["PERSON"], document_id=doc_a)
        s.commit()

    app = _app(keyservice_database_url, monkeypatch, key)
    body = {"document_id": str(doc_a), "grant_id": "g", "assertion": _assertion(key),
           "tokens": [token_a, token_b], "view": "text"}
    with _client(app) as client:
        resp = client.post("/v1/reveal", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["resolved_tokens"] == [token_a]
    assert data["values"] == {token_a: "Jan Jansen"}
    assert token_b not in data["resolved_tokens"]
    assert "Piet Pietersen" not in resp.text


def test_an_authorized_but_unrequested_token_is_not_revealed(
        keyservice_session_factory, keyservice_database_url, monkeypatch, key):
    doc_id = uuid.uuid4()
    with keyservice_session_factory() as s:
        _seed_document(s, doc_id)
        token = _seed_token(s, doc_id, "PERSON", "Jan Jansen")
        _seed_grant(s, "g", "ontvanger@example.com", ["PERSON"], document_id=doc_id)
        s.commit()
    app = _app(keyservice_database_url, monkeypatch, key)
    body = {"document_id": str(doc_id), "grant_id": "g", "assertion": _assertion(key),
           "tokens": [], "view": "text"}
    with _client(app) as client:
        resp = client.post("/v1/reveal", json=body)
    assert resp.status_code == 200
    assert resp.json()["resolved_tokens"] == []
    assert resp.json()["values"] == {}
    assert "Jan Jansen" not in resp.text
    assert token not in resp.text


def test_a_missing_key_version_leaves_the_token_unresolved(
        keyservice_session_factory, keyservice_database_url, monkeypatch, key):
    doc_id = uuid.uuid4()
    with keyservice_session_factory() as s:
        _seed_document(s, doc_id)
        token = _seed_token(s, doc_id, "PERSON", "Jan Jansen")
        _seed_grant(s, "g", "ontvanger@example.com", ["PERSON"], document_id=doc_id)
        s.commit()
        # Drop the key vault row so the mapping's key_id no longer resolves.
        from wordsworth.keyservice.models import KeyVaultRecord
        s.query(KeyVaultRecord).delete()
        s.commit()
    app = _app(keyservice_database_url, monkeypatch, key)
    body = {"document_id": str(doc_id), "grant_id": "g", "assertion": _assertion(key),
           "tokens": [token], "view": "text"}
    with _client(app) as client:
        resp = client.post("/v1/reveal", json=body)
    assert resp.status_code == 200
    assert resp.json()["resolved_tokens"] == []


def test_transit_down_is_503_and_writes_no_record(
        keyservice_session_factory, keyservice_database_url, monkeypatch, key):
    doc_id = uuid.uuid4()
    with keyservice_session_factory() as s:
        _seed_document(s, doc_id)
        token = _seed_token(s, doc_id, "PERSON", "Jan Jansen")
        _seed_grant(s, "g", "ontvanger@example.com", ["PERSON"], document_id=doc_id)
        s.commit()
    app = _app(keyservice_database_url, monkeypatch, key,
              transit_for=lambda kek: _RefusingTransit())
    body = {"document_id": str(doc_id), "grant_id": "g", "assertion": _assertion(key),
           "tokens": [token], "view": "text"}
    with _client(app) as client:
        resp = client.post("/v1/reveal", json=body)
    assert resp.status_code == 503
    assert resp.json() == {"detail": "key service unavailable"}
    with keyservice_session_factory() as s:
        assert s.query(AccessAudit).count() == 0


def test_the_pdf_view_returns_resolved_tokens_and_no_values(
        keyservice_session_factory, keyservice_database_url, monkeypatch, key):
    doc_id = uuid.uuid4()
    with keyservice_session_factory() as s:
        _seed_document(s, doc_id)
        token = _seed_token(s, doc_id, "PERSON", "Jan Jansen")
        _seed_grant(s, "g", "ontvanger@example.com", ["PERSON"], document_id=doc_id)
        s.commit()
    app = _app(keyservice_database_url, monkeypatch, key)
    body = {"document_id": str(doc_id), "grant_id": "g", "assertion": _assertion(key),
           "tokens": [token], "view": "pdf"}
    with _client(app) as client:
        resp = client.post("/v1/reveal", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert "values" not in data
    assert data["resolved_tokens"] == [token]
    assert "Jan Jansen" not in resp.text


# --- the audit record -------------------------------------------------------

def test_a_successful_reveal_appends_one_access_audit_record_and_the_chain_verifies(
        keyservice_session_factory, keyservice_database_url, monkeypatch, key):
    doc_id = uuid.uuid4()
    with keyservice_session_factory() as s:
        _seed_document(s, doc_id)
        token = _seed_token(s, doc_id, "PERSON", "Jan Jansen")
        _seed_grant(s, "g", "ontvanger@example.com", ["PERSON"], document_id=doc_id)
        s.commit()
    app = _app(keyservice_database_url, monkeypatch, key)
    body = {"document_id": str(doc_id), "grant_id": "g", "assertion": _assertion(key),
           "tokens": [token], "view": "text"}
    with _client(app) as client:
        resp = client.post("/v1/reveal", json=body)
    assert resp.status_code == 200
    data = resp.json()

    with keyservice_session_factory() as s:
        records = s.query(AccessAudit).all()
        from wordsworth.keyservice.audit import verify_access_chain
        ok, bad = verify_access_chain(s)
    assert ok is True and bad is None
    assert len(records) == 1
    record = records[0]
    assert record.event == "reveal"
    assert record.service_caller == "wordsworth"
    assert record.caller == "ontvanger@example.com"
    assert record.document_id == doc_id
    assert record.payload["actor"] == "ontvanger@example.com"
    assert record.payload["grant_id"] == "g"
    assert record.payload["pseudonyms"] == [token]
    assert record.payload["types"] == ["PERSON"]
    assert "Jan Jansen" not in str(record.payload)
    assert data["resolved_types"] == record.payload["types"]


def test_a_refusal_writes_no_record(
        keyservice_session_factory, keyservice_database_url, monkeypatch, key):
    doc_id, other_id = uuid.uuid4(), uuid.uuid4()
    with keyservice_session_factory() as s:
        _seed_document(s, doc_id)
        grants = _grant_causes(s, doc_id, other_id)
        s.commit()
    app = _app(keyservice_database_url, monkeypatch, key)
    with _client(app) as client:
        for grant_id in grants.values():
            client.post("/v1/reveal", json={
                "document_id": str(doc_id), "grant_id": grant_id,
                "assertion": _assertion(key), "tokens": [], "view": "text"})
    with keyservice_session_factory() as s:
        assert s.query(AccessAudit).count() == 0


def test_a_refusal_logs_nothing_about_its_cause(
        keyservice_session_factory, keyservice_database_url, monkeypatch, key, caplog):
    doc_id, other_id = uuid.uuid4(), uuid.uuid4()
    with keyservice_session_factory() as s:
        _seed_document(s, doc_id)
        grants = _grant_causes(s, doc_id, other_id)
        s.commit()
    app = _app(keyservice_database_url, monkeypatch, key)
    forbidden_words = ("unknown", "superseded", "deleted")
    with _client(app) as client:
        for grant_id in grants.values():
            caplog.clear()
            with caplog.at_level(logging.DEBUG):
                resp = client.post("/v1/reveal", json={
                    "document_id": str(doc_id), "grant_id": grant_id,
                    "assertion": _assertion(key), "tokens": [], "view": "text"})
            assert resp.status_code == 403
            for rec in caplog.records:
                lowered = rec.getMessage().lower()
                assert not any(w in lowered for w in forbidden_words)
                assert str(doc_id) not in rec.getMessage()


# --- decided afresh ----------------------------------------------------------

def test_a_grant_revoked_between_decide_and_reveal_makes_reveal_403(
        keyservice_session_factory, keyservice_database_url, monkeypatch, key):
    doc_id = uuid.uuid4()
    with keyservice_session_factory() as s:
        _seed_document(s, doc_id)
        _seed_grant(s, "g", "ontvanger@example.com", ["PERSON"], document_id=doc_id)
        s.commit()
    app = _app(keyservice_database_url, monkeypatch, key)
    body = {"document_id": str(doc_id), "grant_id": "g", "assertion": _assertion(key)}
    with _client(app) as client:
        decide_resp = client.post("/v1/reveal/decide", json=body)
        assert decide_resp.status_code == 200
        with keyservice_session_factory() as s:
            row = s.get(GrantRecord, "g")
            row.status = "revoked"
            s.commit()
        reveal_resp = client.post("/v1/reveal", json={**body, "tokens": [], "view": "text"})
    assert reveal_resp.status_code == 403
    assert reveal_resp.json() == REFUSAL


def test_a_role_switched_off_between_decide_and_reveal_makes_reveal_403(
        keyservice_session_factory, keyservice_database_url, monkeypatch, key):
    from wordsworth.keyservice.roles import ADMIN
    doc_id = uuid.uuid4()
    with keyservice_session_factory() as s:
        _seed_document(s, doc_id)
        _seed_admin_role(s)
        _seed_grant(s, "g", "ontvanger@example.com", [], document_id=doc_id, role=ADMIN)
        s.commit()
    app = _app(keyservice_database_url, monkeypatch, key)
    body = {"document_id": str(doc_id), "grant_id": "g", "assertion": _assertion(key)}
    with _client(app) as client:
        decide_resp = client.post("/v1/reveal/decide", json=body)
        assert decide_resp.status_code == 200
        assert decide_resp.json()["authorized_types"]
        with keyservice_session_factory() as s:
            role = s.query(Role).filter_by(name=ADMIN).first()
            role.active = False
            s.commit()
        reveal_resp = client.post("/v1/reveal", json={**body, "tokens": [], "view": "text"})
    assert reveal_resp.status_code == 403
    assert reveal_resp.json() == REFUSAL
