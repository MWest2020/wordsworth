"""Grant admin API — issue / inspect / revoke (add-grant-api).

Local/fast: an InMemoryGrantStore + a fake session_factory (the store ignores
the session), so the CRUD surface is provable without a DB. The revoke→reveal
enforcement is covered in test_grant_api_db.py (CI, real Postgres)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from wordsworth.api import create_app
from wordsworth.grants import InMemoryGrantStore
from wordsworth.key_audit import JsonlKeyLifecycleAudit

DOC = "8b4ad8ad-123b-406a-bdfa-4b30aed9199b"


class _FakeSession:
    """Stand-in session: the in-memory grant store ignores it, and `get` only
    has to answer the existence check that `POST /grants` does on the document
    it is scoped to."""

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def commit(self):
        pass

    def get(self, _model, pk):
        return object() if str(pk) == DOC else None


def _app(gs, tmp_path, allow_global_grants=False):
    return create_app(session_factory=lambda: _FakeSession(), grant_store=gs,
                      key_audit=JsonlKeyLifecycleAudit(tmp_path / "ka.jsonl"),
                      allow_global_grants=allow_global_grants)


def test_issue_get_revoke_lifecycle(tmp_path):
    gs = InMemoryGrantStore()
    c = TestClient(_app(gs, tmp_path))
    r = c.post("/grants", json={"recipient": "team-a",
                                "allowed_types": ["person", "EMAIL"],
                                "document_id": DOC})
    assert r.status_code == 201
    body = r.json()
    gid = body["grant_id"]
    assert body["status"] == "active"
    assert set(body["allowed_types"]) == {"PERSON", "EMAIL"}   # upper-cased
    assert c.get(f"/grants/{gid}").json()["status"] == "active"
    rv = c.post(f"/grants/{gid}/revoke")
    assert rv.status_code == 200 and rv.json()["status"] == "revoked"
    assert c.get(f"/grants/{gid}").json()["status"] == "revoked"


def test_revoke_is_idempotent(tmp_path):
    gs = InMemoryGrantStore()
    c = TestClient(_app(gs, tmp_path))
    gid = c.post("/grants", json={"recipient": "r", "allowed_types": ["PERSON"],
                                  "document_id": DOC}).json()["grant_id"]
    assert c.post(f"/grants/{gid}/revoke").json()["status"] == "revoked"
    assert c.post(f"/grants/{gid}/revoke").json()["status"] == "revoked"   # again, fine


def test_unknown_grant_404(tmp_path):
    c = TestClient(_app(InMemoryGrantStore(), tmp_path))
    assert c.get("/grants/nope").status_code == 404
    assert c.post("/grants/nope/revoke").status_code == 404


def test_scope_and_expiry_echoed(tmp_path):
    c = TestClient(_app(InMemoryGrantStore(), tmp_path))
    exp = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    r = c.post("/grants", json={"recipient": "r", "allowed_types": ["PERSON"],
                                "document_id": DOC, "expires_at": exp})
    assert r.status_code == 201
    assert r.json()["document_id"] == DOC and r.json()["expires_at"] is not None


def test_naive_expiry_rejected(tmp_path):
    c = TestClient(_app(InMemoryGrantStore(), tmp_path))
    r = c.post("/grants", json={"recipient": "r", "allowed_types": ["PERSON"],
                                "document_id": DOC,
                                "expires_at": "2026-12-31T00:00:00"})   # no tz
    assert r.status_code == 400


def test_malformed_inputs_rejected(tmp_path):
    c = TestClient(_app(InMemoryGrantStore(), tmp_path))
    assert c.post("/grants", json={"recipient": "r", "allowed_types": ["P"],
                                   "document_id": DOC,
                                   "expires_at": "nonsense"}).status_code == 400
    assert c.post("/grants", json={"recipient": "r", "allowed_types": ["P"],
                                   "document_id": "not-a-uuid"}).status_code == 400


def test_response_carries_no_key_material(tmp_path):
    c = TestClient(_app(InMemoryGrantStore(), tmp_path))
    body = c.post("/grants", json={"recipient": "r", "allowed_types": ["PERSON"],
                                   "document_id": DOC}).json()
    # ``ppl`` (add-pii-categories-and-ppl) is derived from allowed_types — metadata,
    # not material.
    assert set(body) == {"grant_id", "recipient", "allowed_types", "ppl", "document_id",
                         "domain",
                         "status", "created_at", "revoked_at", "expires_at"}


def test_routes_absent_without_grant_store():
    c = TestClient(create_app(session_factory=lambda: _FakeSession()))
    spec = c.get("/openapi.json").json()
    assert "/grants" not in spec["paths"]
    assert c.post("/grants", json={"recipient": "r", "allowed_types": ["P"]}).status_code == 404


def test_unscoped_issue_refused_while_global_grants_disallowed(tmp_path):
    """The default path cannot mint a reveal-everything grant by omission
    (harden-global-grant-gate): no grant row, no audit event."""
    gs = InMemoryGrantStore()
    ka = tmp_path / "ka.jsonl"
    c = TestClient(_app(gs, tmp_path))
    r = c.post("/grants", json={"recipient": "r", "allowed_types": ["PERSON"]})
    assert r.status_code == 400
    assert "document_id" in r.json()["detail"]
    assert not ka.exists() or ka.read_text(encoding="utf-8") == ""


def test_unscoped_issue_allowed_when_deployment_opts_in(tmp_path):
    c = TestClient(_app(InMemoryGrantStore(), tmp_path, allow_global_grants=True))
    r = c.post("/grants", json={"recipient": "r", "allowed_types": ["PERSON"]})
    assert r.status_code == 201 and r.json()["document_id"] is None


def test_grant_admin_open_zonder_auth(tmp_path):
    """Zonder api-key-auth is er geen caller om op te beslissen: gedrag ongewijzigd
    (de gedocumenteerde tailnet-interne modus)."""
    c = TestClient(_app(InMemoryGrantStore(), tmp_path))
    r = c.post("/grants", json={"recipient": "r", "allowed_types": ["PERSON"],
                                "document_id": DOC})
    assert r.status_code == 201


def _app_auth(gs, tmp_path, issuers):
    return create_app(session_factory=lambda: _FakeSession(), grant_store=gs,
                      key_audit=JsonlKeyLifecycleAudit(tmp_path / "ka.jsonl"),
                      api_keys={"k-issuer": "issuer", "k-plain": "plain"},
                      grant_issuer_labels=issuers)


def test_grant_uitgeven_alleen_door_een_issuer_label(tmp_path):
    """Met auth aan is een grant minten het zwaarste recht: alleen expliciet
    genoemde labels. Een gewone geauthenticeerde caller mag het niet."""
    c = TestClient(_app_auth(InMemoryGrantStore(), tmp_path, ["issuer"]))
    body = {"recipient": "r", "allowed_types": ["PERSON"], "document_id": DOC}
    assert c.post("/grants", json=body, headers={"X-API-Key": "k-issuer"}).status_code == 201
    r = c.post("/grants", json=body, headers={"X-API-Key": "k-plain"})
    assert r.status_code == 403 and "grants" in r.json()["detail"]


def test_lege_issuerlijst_weigert_iedereen_met_auth_aan(tmp_path):
    """Leeg betekent hier NIET 'iedereen mag' (anders dan bij corpus-read): wie
    vergeet de kring te benoemen, mint niets."""
    c = TestClient(_app_auth(InMemoryGrantStore(), tmp_path, []))
    r = c.post("/grants", json={"recipient": "r", "allowed_types": ["PERSON"],
                                "document_id": DOC},
               headers={"X-API-Key": "k-issuer"})
    assert r.status_code == 403


def test_intrekken_valt_onder_dezelfde_scope(tmp_path):
    gs = InMemoryGrantStore()
    c = TestClient(_app_auth(gs, tmp_path, ["issuer"]))
    gid = c.post("/grants", json={"recipient": "r", "allowed_types": ["PERSON"],
                                  "document_id": DOC},
                 headers={"X-API-Key": "k-issuer"}).json()["grant_id"]
    assert c.post(f"/grants/{gid}/revoke",
                  headers={"X-API-Key": "k-plain"}).status_code == 403
    assert c.post(f"/grants/{gid}/revoke",
                  headers={"X-API-Key": "k-issuer"}).json()["status"] == "revoked"


def test_issue_with_unknown_document_is_404_and_writes_nothing(tmp_path):
    """A well-formed document_id that does not exist used to fall through to the
    INSERT and come back as a 500 with a ForeignKeyViolation. It is a client
    error, and it must not leave a grant or an audit event behind."""
    gs = InMemoryGrantStore()
    audit = tmp_path / "ka.jsonl"
    c = TestClient(create_app(session_factory=lambda: _FakeSession(), grant_store=gs,
                              key_audit=JsonlKeyLifecycleAudit(audit)))

    r = c.post("/grants", json={"recipient": "team-a", "ppl": 1,
                                "document_id": "00000000-0000-0000-0000-000000000000"})

    assert r.status_code == 404
    assert r.json()["detail"] == "unknown document"
    assert gs._d == {}
    assert not audit.exists() or audit.read_text() == ""


def test_issue_with_known_document_still_mints(tmp_path):
    gs = InMemoryGrantStore()
    c = TestClient(_app(gs, tmp_path))

    r = c.post("/grants", json={"recipient": "team-a", "ppl": 1,
                                "document_id": DOC})

    assert r.status_code == 201
    assert r.json()["document_id"] == DOC
