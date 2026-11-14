"""Revoking a grant names who revoked it (#443).

`POST /grants/{id}/revoke` used to audit the literal "operator", so the
key-lifecycle trail could not say who withdrew a grant. It now records the
authenticated caller, the same way issuing a grant already did."""
from __future__ import annotations

from fastapi.testclient import TestClient

from wordsworth.api import create_app
from wordsworth.grants import InMemoryGrantStore
from wordsworth.key_audit import (
    GRANT_ISSUED_ACTION,
    GRANT_REVOKED_ACTION,
    JsonlKeyLifecycleAudit,
)

DOC = "8b4ad8ad-123b-406a-bdfa-4b30aed9199b"
BODY = {"recipient": "r", "allowed_types": ["PERSON"], "document_id": DOC}


class _FakeSession:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def commit(self):
        pass

    def get(self, _model, pk):
        return object() if str(pk) == DOC else None


def _client(ka, **kw):
    return TestClient(create_app(session_factory=lambda: _FakeSession(),
                                 grant_store=InMemoryGrantStore(),
                                 key_audit=ka, **kw))


def test_grant_revoked_names_the_caller(tmp_path):
    ka = JsonlKeyLifecycleAudit(tmp_path / "ka.jsonl")
    c = _client(ka, api_keys={"k-mark": "mark", "k-anna": "anna"},
                grant_issuer_labels=["mark", "anna"])
    gid = c.post("/grants", json=BODY,
                 headers={"X-API-Key": "k-mark"}).json()["grant_id"]

    r = c.post(f"/grants/{gid}/revoke", headers={"X-API-Key": "k-anna"})

    assert r.status_code == 200
    issued, revoked = ka.events()
    assert issued["action"] == GRANT_ISSUED_ACTION and issued["actor"] == "mark"
    assert revoked["action"] == GRANT_REVOKED_ACTION
    assert revoked["grant_id"] == gid
    assert revoked["actor"] == "anna"


def test_grant_revoked_without_auth_says_nobody_is_known(tmp_path):
    """Without auth there is no caller to name; the trail says so instead of
    inventing an "operator"."""
    ka = JsonlKeyLifecycleAudit(tmp_path / "ka.jsonl")
    c = _client(ka)
    gid = c.post("/grants", json=BODY).json()["grant_id"]

    c.post(f"/grants/{gid}/revoke")

    revoked = ka.events()[-1]
    assert revoked["action"] == GRANT_REVOKED_ACTION
    assert revoked["actor"] == "onbekend"
