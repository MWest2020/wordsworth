# SPDX-License-Identifier: MIT
"""The group→role mapping endpoints (keycloak-groups-to-roles): behind the
same gate as `/roles`, idempotent, 404 on an unknown role, and audited with
the person who changed it as actor."""
from __future__ import annotations

from fastapi.testclient import TestClient

from wordsworth.api import create_app
from wordsworth.key_audit import JsonlKeyLifecycleAudit

KEYS = {"s3cret": "mark"}
KOP = {"x-api-key": "s3cret"}


def _app(session_factory, **extra):
    return create_app(session_factory=session_factory, api_keys=KEYS,
                      grant_issuer_labels=["mark"], **extra)


def _client(session_factory, **extra):
    return TestClient(_app(session_factory, **extra), base_url="https://testserver")


def test_mapping_an_unknown_role_is_a_404(session_factory):
    c = _client(session_factory)
    assert c.put("/group-roles/ict/weg", headers=KOP).status_code == 404


def test_map_and_list_a_group(session_factory):
    c = _client(session_factory)
    c.post("/roles", headers=KOP, json={"name": "beheerder", "allowed_types": []})
    r = c.put("/group-roles/ict/beheerder", headers=KOP)
    assert r.status_code == 200
    body = r.json()
    assert body["group"] == "ict" and body["role"] == "beheerder"
    assert body["created_by"] == "mark"
    assert [(g["group"], g["role"]) for g in c.get("/group-roles", headers=KOP).json()
           ] == [("ict", "beheerder")]


def test_mapping_an_already_mapped_pair_is_idempotent(session_factory):
    c = _client(session_factory)
    c.post("/roles", headers=KOP, json={"name": "beheerder", "allowed_types": []})
    c.put("/group-roles/ict/beheerder", headers=KOP)
    c.put("/group-roles/ict/beheerder", headers=KOP)
    assert len(c.get("/group-roles", headers=KOP).json()) == 1


def test_unmapping_an_absent_pair_is_idempotent(session_factory):
    c = _client(session_factory)
    c.post("/roles", headers=KOP, json={"name": "beheerder", "allowed_types": []})
    r = c.delete("/group-roles/ict/beheerder", headers=KOP)
    assert r.status_code == 200
    assert c.get("/group-roles", headers=KOP).json() == []


def test_unmap_a_group(session_factory):
    c = _client(session_factory)
    c.post("/roles", headers=KOP, json={"name": "beheerder", "allowed_types": []})
    c.put("/group-roles/ict/beheerder", headers=KOP)
    assert c.delete("/group-roles/ict/beheerder", headers=KOP).status_code == 200
    assert c.get("/group-roles", headers=KOP).json() == []


def test_group_roles_are_behind_the_grant_admin_gate(session_factory):
    app = create_app(session_factory=session_factory, api_keys=KEYS,
                     grant_issuer_labels=["iemand-anders"])
    c = TestClient(app, base_url="https://testserver")
    assert c.get("/group-roles", headers=KOP).status_code == 403
    assert c.put("/group-roles/ict/beheerder", headers=KOP).status_code == 403
    assert c.delete("/group-roles/ict/beheerder", headers=KOP).status_code == 403


def test_mapping_and_unmapping_are_audited_with_the_person(session_factory, tmp_path):
    audit = JsonlKeyLifecycleAudit(tmp_path / "lifecycle.jsonl")
    c = TestClient(_app(session_factory, key_audit=audit),
                  base_url="https://testserver")
    c.post("/roles", headers=KOP, json={"name": "beheerder", "allowed_types": []})
    c.put("/group-roles/ict/beheerder", headers=KOP)
    c.delete("/group-roles/ict/beheerder", headers=KOP)

    events = [e for e in audit.events()
             if e.get("action") in ("group_role_mapped", "group_role_unmapped")]
    assert [e["action"] for e in events] == ["group_role_mapped", "group_role_unmapped"]
    for e in events:
        assert e["group"] == "ict" and e["role"] == "beheerder"
        assert e["actor"] == "mark"


def test_an_idempotent_put_or_delete_writes_no_event(session_factory, tmp_path):
    audit = JsonlKeyLifecycleAudit(tmp_path / "lifecycle.jsonl")
    c = TestClient(_app(session_factory, key_audit=audit),
                  base_url="https://testserver")
    c.post("/roles", headers=KOP, json={"name": "beheerder", "allowed_types": []})
    c.put("/group-roles/ict/beheerder", headers=KOP)
    c.put("/group-roles/ict/beheerder", headers=KOP)   # idempotent: no 2nd event
    c.delete("/group-roles/weg/beheerder", headers=KOP)  # absent pair: no event

    events = [e for e in audit.events() if e.get("action") == "group_role_mapped"]
    assert len(events) == 1
