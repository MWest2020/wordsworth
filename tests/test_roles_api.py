# SPDX-License-Identifier: MIT
"""De rol-endpoints en wat ze met een onthulling doen (rollen).

De belangrijkste test hier is de laatste: een rol uitzetten terwijl er een
geldige grant op staat, en zien dat de onthulling 403 geeft. Dat is de belofte
waarvoor deze hele vorm gekozen is.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from wordsworth.api import create_app
from wordsworth.grants import PostgresGrantStore
from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.pipeline import ingest, process
from wordsworth.pseudonymizer import Pseudonymizer

PII_EMAIL = "jan.jansen@haarlem.nl"
PII_BSN = "123456782"
KEYS = {"s3cret": "mark"}
KOP = {"x-api-key": "s3cret"}


def _app(session_factory, kp=None, **extra):
    return create_app(session_factory=session_factory, api_keys=KEYS,
                      grant_issuer_labels=["mark"],
                      corpus_read_labels=["mark"], key_provider=kp,
                      grant_store_factory=lambda s: PostgresGrantStore(s),
                      **extra)


def _client(session_factory, kp=None, **extra):
    return TestClient(_app(session_factory, kp, **extra),
                      base_url="https://testserver")


def _document(session_factory, mem_store, mem_index, fake_embedder, pdf):
    kp = InMemoryKeyProvider()
    with session_factory() as s:
        doc = ingest(s, mem_store, pdf)
        s.commit()
        process(s, doc.id, mem_store,
                anonymizer=Pseudonymizer(kp, PostgresMappingStore(s)),
                search_index=mem_index, embedder=fake_embedder)
        s.commit()
        return kp, doc.id


def test_create_and_list_a_role(session_factory):
    c = _client(session_factory)
    r = c.post("/roles", headers=KOP,
               json={"name": "hr", "allowed_types": ["person", "email"]})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "hr"
    assert body["allowed_types"] == ["EMAIL", "PERSON"]
    assert body["active"] is True
    assert body["created_by"] == "mark", "wie de rol maakte hoort in het spoor"
    assert [x["name"] for x in c.get("/roles", headers=KOP).json()] == ["hr"]


def test_a_role_carries_no_scope(session_factory):
    """De scope hoort bij het toekennen, niet bij de rol. Dezelfde rol kan aan
    de een gegeven worden voor één document en aan de ander voor alles."""
    c = _client(session_factory)
    body = c.post("/roles", headers=KOP,
                  json={"name": "hr", "allowed_types": ["PERSON"]}).json()
    assert "document_id" not in body and "scope" not in body


def test_a_duplicate_name_is_a_400(session_factory):
    c = _client(session_factory)
    c.post("/roles", headers=KOP, json={"name": "hr", "allowed_types": ["PERSON"]})
    r = c.post("/roles", headers=KOP, json={"name": "hr", "allowed_types": ["BSN"]})
    assert r.status_code == 400


def test_switching_needs_a_reason(session_factory):
    c = _client(session_factory)
    c.post("/roles", headers=KOP, json={"name": "hr", "allowed_types": ["PERSON"]})
    assert c.post("/roles/hr/deactivate", headers=KOP,
                  json={"reason": "  "}).status_code == 400
    assert c.get("/roles", headers=KOP).json()[0]["active"] is True


def test_an_unknown_role_is_a_404(session_factory):
    c = _client(session_factory)
    assert c.post("/roles/weg/deactivate", headers=KOP,
                  json={"reason": "x"}).status_code == 404
    assert c.put("/roles/weg/types", headers=KOP,
                 json={"allowed_types": ["PERSON"]}).status_code == 404


def test_roles_are_behind_the_grant_admin_gate(session_factory):
    """Wie bepaalt wat een rol mag, bepaalt wat iedereen met die rol mag zien.
    Dat is geen kleiner recht dan een grant uitgeven."""
    app = create_app(session_factory=session_factory, api_keys=KEYS,
                     grant_issuer_labels=["iemand-anders"])
    c = TestClient(app, base_url="https://testserver")
    assert c.get("/roles", headers=KOP).status_code == 403
    assert c.post("/roles", headers=KOP,
                  json={"name": "x", "allowed_types": []}).status_code == 403


def test_a_grant_names_exactly_one_source(session_factory):
    c = _client(session_factory)
    c.post("/roles", headers=KOP, json={"name": "hr", "allowed_types": ["EMAIL"]})
    # types én rol
    r = c.post("/grants", headers=KOP, json={
        "recipient": "mark", "allowed_types": ["EMAIL"], "role": "hr",
        "document_id": "00000000-0000-0000-0000-000000000000"})
    assert r.status_code == 422
    # geen van beide
    r = c.post("/grants", headers=KOP, json={"recipient": "mark"})
    assert r.status_code == 422


def test_a_grant_on_an_unknown_role_is_refused_now(session_factory):
    """Een grant op een rol die niet bestaat is een grant die niets doet. Dat
    hoort nu te blijken en niet bij de eerste onthulling."""
    c = _client(session_factory)
    r = c.post("/grants", headers=KOP, json={
        "recipient": "mark", "role": "bestaat-niet",
        "document_id": "00000000-0000-0000-0000-000000000000"})
    assert r.status_code == 404


def test_an_unscoped_grant_needs_the_admin_role(session_factory):
    """De ongescopete grant blijft geweigerd — behalve op naam van de
    beheerdersrol. De vlag omzetten zou hem voor iedereen openen."""
    c = _client(session_factory)
    c.post("/roles", headers=KOP, json={"name": "hr", "allowed_types": ["EMAIL"]})
    c.post("/roles", headers=KOP, json={"name": "beheerder",
                                        "allowed_types": ["EMAIL", "BSN"]})
    assert c.post("/grants", headers=KOP,
                  json={"recipient": "mark", "role": "hr"}).status_code == 400
    assert c.post("/grants", headers=KOP,
                  json={"recipient": "mark", "role": "beheerder"}).status_code == 201
    assert c.post("/grants", headers=KOP,
                  json={"recipient": "mark",
                        "allowed_types": ["EMAIL"]}).status_code == 400


def test_switching_a_role_off_stops_a_reveal_that_was_working(
        session_factory, mem_store, mem_index, fake_embedder, born_digital_pii_pdf):
    """De hele reden voor deze vorm, langs de echte weg gemeten.

    Eerst onthult hij. Dan gaat de rol uit. Dan geeft dezelfde grant 403 — en
    de grant zelf is niet aangeraakt.
    """
    kp, doc_id = _document(session_factory, mem_store, mem_index, fake_embedder,
                           born_digital_pii_pdf)
    c = _client(session_factory, kp)
    c.post("/roles", headers=KOP, json={"name": "hr", "allowed_types": ["EMAIL"]})
    grant = c.post("/grants", headers=KOP, json={
        "recipient": "mark", "role": "hr", "document_id": str(doc_id)}).json()

    eerst = c.post(f"/documents/{doc_id}/reveal", headers=KOP,
                   json={"grant_id": grant["grant_id"], "types": ["EMAIL"]})
    assert eerst.status_code == 200
    assert PII_EMAIL in eerst.json()["revealed_text"]
    assert eerst.json()["resolved_types"] == ["EMAIL"]

    uit = c.post("/roles/hr/deactivate", headers=KOP,
                 json={"reason": "sleutel gelekt"})
    assert uit.status_code == 200 and uit.json()["active"] is False

    daarna = c.post(f"/documents/{doc_id}/reveal", headers=KOP,
                    json={"grant_id": grant["grant_id"], "types": ["EMAIL"]})
    assert daarna.status_code == 403

    nog_steeds = c.get(f"/grants/{grant['grant_id']}", headers=KOP).json()
    assert nog_steeds["status"].lower() == "active", (
        "er is een grant ingetrokken; dan is dit een sjabloon en geen rol")

    # En weer aan: de onthulling werkt weer, zonder een nieuwe grant.
    c.post("/roles/hr/activate", headers=KOP, json={"reason": "sleutel vervangen"})
    weer = c.post(f"/documents/{doc_id}/reveal", headers=KOP,
                  json={"grant_id": grant["grant_id"], "types": ["EMAIL"]})
    assert weer.status_code == 200


def test_narrowing_a_role_narrows_a_live_grant(
        session_factory, mem_store, mem_index, fake_embedder, born_digital_pii_pdf):
    kp, doc_id = _document(session_factory, mem_store, mem_index, fake_embedder,
                           born_digital_pii_pdf)
    c = _client(session_factory, kp)
    c.post("/roles", headers=KOP,
           json={"name": "hr", "allowed_types": ["EMAIL", "BSN"]})
    grant = c.post("/grants", headers=KOP, json={
        "recipient": "mark", "role": "hr", "document_id": str(doc_id)}).json()
    eerst = c.post(f"/documents/{doc_id}/reveal", headers=KOP,
                   json={"grant_id": grant["grant_id"], "types": ["BSN"]}).json()
    assert PII_BSN in eerst["revealed_text"]

    c.put("/roles/hr/types", headers=KOP, json={"allowed_types": ["EMAIL"]})
    daarna = c.post(f"/documents/{doc_id}/reveal", headers=KOP,
                    json={"grant_id": grant["grant_id"], "types": ["BSN"]})
    # 200 met een ingehouden type, niet 403: dat is hoe deze API een gevraagd
    # type behandelt dat niet mag. Een rol inperken is geen andere soort
    # weigering dan een type dat nooit in de grant stond, en het zou verwarrend
    # zijn als hetzelfde gebrek aan recht twee verschillende codes gaf.
    assert daarna.status_code == 200
    body = daarna.json()
    assert PII_BSN not in body["revealed_text"], "de rol is ingeperkt"
    assert body["resolved_types"] == []
    assert body["withheld_types"] == ["BSN"]

    # Pas als de rol niets meer toestaat, doet de grant niets: dan 403.
    c.put("/roles/hr/types", headers=KOP, json={"allowed_types": []})
    leeg = c.post(f"/documents/{doc_id}/reveal", headers=KOP,
                  json={"grant_id": grant["grant_id"], "types": ["EMAIL"]})
    assert leeg.status_code == 403


def test_the_audit_says_under_which_role_it_was_allowed(
        session_factory, mem_store, mem_index, fake_embedder, born_digital_pii_pdf):
    """Zonder de rolnaam is later niet na te vertellen waaróm dit mocht — en bij
    een ongescopete grant ook niet dát er een uitzondering gold."""
    from sqlalchemy import select

    from wordsworth.models import AuditRecord

    kp, doc_id = _document(session_factory, mem_store, mem_index, fake_embedder,
                           born_digital_pii_pdf)
    c = _client(session_factory, kp)
    c.post("/roles", headers=KOP,
           json={"name": "beheerder", "allowed_types": ["EMAIL"]})
    grant = c.post("/grants", headers=KOP, json={
        "recipient": "mark", "role": "beheerder"}).json()
    assert c.post(f"/documents/{doc_id}/reveal", headers=KOP,
                  json={"grant_id": grant["grant_id"],
                        "types": ["EMAIL"]}).status_code == 200

    with session_factory() as s:
        payload = s.execute(
            select(AuditRecord.payload)
            .where(AuditRecord.document_id == doc_id,
                   AuditRecord.step == "deanonymize")
            .order_by(AuditRecord.seq.desc()).limit(1)).scalar_one()
    assert payload["role"] == "beheerder"
    assert payload["global_by_role"] is True


def _stroom(tmp_path):
    from wordsworth.key_audit import JsonlKeyLifecycleAudit

    return JsonlKeyLifecycleAudit(tmp_path / "lifecycle.jsonl")


def test_the_trail_names_who_pulled_the_emergency_stop(session_factory, tmp_path):
    """De spec-eis: het uitzetten van een rol legt vast wie het deed en waarom.

    Niet in de document-hashketen: die is de toestandsmachine van één document
    en een rol raakt er duizend. Rollen staan waar grants en sleutelrotaties ook
    staan — globale autorisatiefeiten zonder document, in een eigen append-only
    stroom.
    """
    audit = _stroom(tmp_path)
    c = TestClient(_app(session_factory, key_audit=audit),
                   base_url="https://testserver")
    c.post("/roles", headers=KOP, json={"name": "hr", "allowed_types": ["EMAIL"]})
    c.post("/roles/hr/deactivate", headers=KOP, json={"reason": "sleutel gelekt"})

    gebeurtenissen = [e for e in audit.events() if e.get("action") == "role_changed"]
    assert [e["change"] for e in gebeurtenissen] == ["created", "deactivated"]
    uit = gebeurtenissen[-1]
    assert uit["role"] == "hr"
    assert uit["actor"] == "mark", "zonder wie is het een storing zonder uitleg"
    assert uit["reason"] == "sleutel gelekt"
    assert uit["active"] is False
    # De stand ná de wijziging staat erbij, zodat uit de stroom zelf te
    # reconstrueren is wat de rol op enig moment toestond.
    assert uit["allowed_types"] == ["EMAIL"]


def test_narrowing_a_role_is_recorded_too(session_factory, tmp_path):
    """Inperken verandert wat iedereen met die rol mag zien. Dat is dezelfde
    soort gebeurtenis als uitzetten, alleen stiller."""
    audit = _stroom(tmp_path)
    c = TestClient(_app(session_factory, key_audit=audit),
                   base_url="https://testserver")
    c.post("/roles", headers=KOP,
           json={"name": "hr", "allowed_types": ["EMAIL", "BSN"]})
    c.put("/roles/hr/types", headers=KOP, json={"allowed_types": ["EMAIL"]})
    laatste = [e for e in audit.events() if e.get("action") == "role_changed"][-1]
    assert laatste["change"] == "types"
    assert laatste["allowed_types"] == ["EMAIL"]


def test_the_console_writes_the_same_record_as_the_api(session_factory, tmp_path):
    """Twee wegen naar dezelfde handeling met maar één spoor eronder is hoe een
    spoor gaten krijgt."""
    audit = _stroom(tmp_path)
    c = TestClient(_app(session_factory, key_audit=audit),
                   base_url="https://testserver")
    c.post("/console/login", data={"key": "s3cret"})
    c.post("/console/roles", data={"name": "hr", "types": ["EMAIL"]})
    c.post("/console/roles/switch",
           data={"name": "hr", "aan": "0", "reason": "via het scherm"})
    uit = [e for e in audit.events() if e.get("action") == "role_changed"][-1]
    assert uit["change"] == "deactivated"
    assert uit["actor"] == "mark" and uit["reason"] == "via het scherm"
