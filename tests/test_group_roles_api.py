# SPDX-License-Identifier: MIT
"""`GET/PUT/DELETE /group-roles` and the console page (keycloak-groups-to-roles).

Same gate as `/roles` (`grant_admin`): an issuer label may, anyone else is
refused. `PUT` on an unknown role is 404, like `PUT /roles/{name}/types`.
Every real change is audited with the person as actor.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from wordsworth.api import create_app
from wordsworth.key_audit import JsonlKeyLifecycleAudit

KEYS = {"s3cret": "mark", "k-derde": "derde"}
KOP = {"x-api-key": "s3cret"}


def _app(session_factory, **extra):
    return create_app(session_factory=session_factory, api_keys=KEYS,
                      grant_issuer_labels=["mark"], **extra)


def _client(session_factory, **extra):
    return TestClient(_app(session_factory, **extra), base_url="https://testserver")


def test_an_issuer_maps_and_lists_and_unmaps(session_factory):
    c = _client(session_factory)
    c.post("/roles", headers=KOP, json={"name": "HR", "allowed_types": ["EMAIL"]})
    r = c.put("/group-roles/hr-afdeling/HR", headers=KOP)
    assert r.status_code == 200
    body = r.json()
    assert body == {"group": "hr-afdeling", "role": "HR", "created_by": "mark",
                    "created_at": body["created_at"]}
    assert [row["group"] for row in c.get("/group-roles", headers=KOP).json()] == [
        "hr-afdeling"]
    assert c.delete("/group-roles/hr-afdeling/HR", headers=KOP).status_code == 204
    assert c.get("/group-roles", headers=KOP).json() == []


def test_putting_an_unknown_role_is_404(session_factory):
    c = _client(session_factory)
    assert c.put("/group-roles/hr-afdeling/weg", headers=KOP).status_code == 404


def test_group_roles_are_behind_the_grant_admin_gate(session_factory):
    c = _client(session_factory)
    headers = {"x-api-key": "k-derde"}
    assert c.get("/group-roles", headers=headers).status_code == 403
    assert c.put("/group-roles/hr-afdeling/HR", headers=headers).status_code == 403
    assert c.delete("/group-roles/hr-afdeling/HR", headers=headers).status_code == 403


def test_putting_the_same_pair_twice_is_idempotent_and_writes_one_event(
        session_factory, tmp_path):
    audit = JsonlKeyLifecycleAudit(tmp_path / "lifecycle.jsonl")
    c = _client(session_factory, key_audit=audit)
    c.post("/roles", headers=KOP, json={"name": "HR", "allowed_types": ["EMAIL"]})
    c.put("/group-roles/hr-afdeling/HR", headers=KOP)
    c.put("/group-roles/hr-afdeling/HR", headers=KOP)
    events = [e for e in audit.events() if e.get("action") == "group_role_mapped"]
    assert len(events) == 1
    assert events[0]["actor"] == "mark", "wie koppelde hoort in het spoor"
    assert events[0]["group"] == "hr-afdeling" and events[0]["role"] == "HR"


def test_deleting_an_absent_pair_is_idempotent_and_writes_no_event(
        session_factory, tmp_path):
    audit = JsonlKeyLifecycleAudit(tmp_path / "lifecycle.jsonl")
    c = _client(session_factory, key_audit=audit)
    assert c.delete("/group-roles/hr-afdeling/HR", headers=KOP).status_code == 204
    assert [e for e in audit.events() if e.get("action") == "group_role_unmapped"] == []


def test_the_console_page_maps_and_unmaps(session_factory):
    c = _client(session_factory)
    c.post("/console/login", data={"key": "s3cret"})
    c.post("/roles", headers=KOP, json={"name": "HR", "allowed_types": ["EMAIL"]})
    r = c.post("/console/group-roles", data={"group": "hr-afdeling", "role": "HR"})
    assert r.status_code in (200, 303)
    with session_factory() as s:
        from wordsworth import group_roles

        assert [row.group for row in group_roles.listing(s)] == ["hr-afdeling"]
    c.post("/console/group-roles/delete", data={"group": "hr-afdeling", "role": "HR"})
    with session_factory() as s:
        from wordsworth import group_roles

        assert group_roles.listing(s) == []
