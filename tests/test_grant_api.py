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
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def commit(self):
        pass


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
