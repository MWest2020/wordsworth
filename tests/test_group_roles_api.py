# SPDX-License-Identifier: MIT
"""Groep -> rol over de API en de console (keycloak-groups-to-roles).

Dezelfde poort als rollen (`beheerder`/grant-admin): wie bepaalt welke groep
welke rol krijgt, bepaalt wat iedereen in die groep mag zien.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from wordsworth.api import create_app

KEYS = {"s3cret": "mark"}
KOP = {"x-api-key": "s3cret"}


def _app(session_factory, **extra):
    return create_app(session_factory=session_factory, api_keys=KEYS,
                      grant_issuer_labels=["mark"], **extra)


def _client(session_factory, **extra):
    return TestClient(_app(session_factory, **extra), base_url="https://testserver")


def test_create_and_list_a_mapping(session_factory):
    c = _client(session_factory)
    c.post("/roles", headers=KOP, json={"name": "hr", "allowed_types": ["PERSON"]})
    r = c.put("/group-roles/hr-afdeling", headers=KOP, json={"role": "hr"})
    assert r.status_code == 200
    body = r.json()
    assert body["group"] == "hr-afdeling"
    assert body["role"] == "hr"
    assert body["created_by"] == "mark"
    assert [m["group"] for m in c.get("/group-roles", headers=KOP).json()] == [
        "hr-afdeling"]


def test_a_mapping_on_an_unknown_role_is_a_404(session_factory):
    """Een afbeelding op een rol die niet bestaat doet niets, en dat hoort nu
    te blijken — net als bij een grant op een onbekende rol."""
    c = _client(session_factory)
    r = c.put("/group-roles/hr-afdeling", headers=KOP, json={"role": "bestaat-niet"})
    assert r.status_code == 404


def test_group_roles_are_behind_the_grant_admin_gate(session_factory):
    app = create_app(session_factory=session_factory, api_keys=KEYS,
                     grant_issuer_labels=["iemand-anders"])
    c = TestClient(app, base_url="https://testserver")
    assert c.get("/group-roles", headers=KOP).status_code == 403
    assert c.put("/group-roles/hr", headers=KOP, json={"role": "hr"}).status_code == 403
    assert c.delete("/group-roles/hr", headers=KOP).status_code == 403


def test_deleting_an_unknown_mapping_is_a_404(session_factory):
    c = _client(session_factory)
    assert c.delete("/group-roles/weg", headers=KOP).status_code == 404


def test_putting_again_replaces_the_role(session_factory):
    c = _client(session_factory)
    c.post("/roles", headers=KOP, json={"name": "hr", "allowed_types": []})
    c.post("/roles", headers=KOP, json={"name": "ict", "allowed_types": []})
    c.put("/group-roles/afdeling", headers=KOP, json={"role": "hr"})
    c.put("/group-roles/afdeling", headers=KOP, json={"role": "ict"})
    lijst = c.get("/group-roles", headers=KOP).json()
    assert len(lijst) == 1 and lijst[0]["role"] == "ict"


def test_the_trail_names_who_mapped_a_group(session_factory, tmp_path):
    from wordsworth.key_audit import JsonlKeyLifecycleAudit

    audit = JsonlKeyLifecycleAudit(tmp_path / "lifecycle.jsonl")
    c = TestClient(_app(session_factory, key_audit=audit), base_url="https://testserver")
    c.post("/roles", headers=KOP, json={"name": "hr", "allowed_types": []})
    c.put("/group-roles/hr-afdeling", headers=KOP, json={"role": "hr"})
    c.delete("/group-roles/hr-afdeling", headers=KOP)
    events = [e for e in audit.events() if e.get("action") == "group_role_changed"]
    assert [e["change"] for e in events] == ["created", "deleted"]
    assert events[0]["actor"] == "mark"
    assert events[0]["group"] == "hr-afdeling" and events[0]["role"] == "hr"


def test_the_console_page_offers_the_mapping(session_factory):
    c = TestClient(_app(session_factory), base_url="https://testserver",
                   follow_redirects=False)
    c.post("/console/login", data={"key": "s3cret"})
    c.post("/roles", headers=KOP, json={"name": "hr", "allowed_types": []})
    r = c.post("/console/roles/groups", data={"group": "hr-afdeling", "role": "hr"})
    assert r.status_code == 303, "redirect-na-post, anders maakt herladen hem opnieuw"
    pagina = c.get("/console/roles").text
    assert "<b>hr-afdeling</b>" in pagina


def test_the_console_mapping_delete_works(session_factory):
    c = TestClient(_app(session_factory), base_url="https://testserver",
                   follow_redirects=False)
    c.post("/console/login", data={"key": "s3cret"})
    c.post("/roles", headers=KOP, json={"name": "hr", "allowed_types": []})
    c.post("/console/roles/groups", data={"group": "hr-afdeling", "role": "hr"})
    c.post("/console/roles/groups/delete", data={"group": "hr-afdeling"})
    assert "<b>hr-afdeling</b>" not in c.get("/console/roles").text


def test_the_console_mapping_form_is_behind_the_admin_gate(session_factory):
    app = create_app(session_factory=session_factory, api_keys={"sk-lezer": "lezer"})
    c = TestClient(app, base_url="https://testserver", follow_redirects=False)
    c.post("/console/login", data={"key": "sk-lezer"})
    assert c.post("/console/roles/groups",
                  data={"group": "g", "role": "hr"}).status_code == 403
    assert c.post("/console/roles/groups/delete",
                  data={"group": "g"}).status_code == 403


def test_the_console_writes_the_same_record_as_the_api(session_factory, tmp_path):
    """Twee wegen naar dezelfde handeling met maar één spoor eronder is hoe een
    spoor gaten krijgt."""
    from wordsworth.key_audit import JsonlKeyLifecycleAudit

    audit = JsonlKeyLifecycleAudit(tmp_path / "lifecycle.jsonl")
    c = TestClient(_app(session_factory, key_audit=audit), base_url="https://testserver")
    c.post("/console/login", data={"key": "s3cret"})
    c.post("/roles", headers=KOP, json={"name": "hr", "allowed_types": []})
    c.post("/console/roles/groups", data={"group": "hr-afdeling", "role": "hr"})
    laatste = [e for e in audit.events() if e.get("action") == "group_role_changed"][-1]
    assert laatste["change"] == "created" and laatste["actor"] == "mark"
