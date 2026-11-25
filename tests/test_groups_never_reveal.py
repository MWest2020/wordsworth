# SPDX-License-Identifier: MIT
"""keycloak-groups-to-roles, task 6: a group-held role never authorises a
reveal. `grants.authorize` is unchanged -- it receives no groups and no held
roles, and a grant still only works for its named recipient."""
from __future__ import annotations

import time

from fastapi.testclient import TestClient
from sqlalchemy import select

from test_access_identity import _jwks, _key, _token
from wordsworth import group_roles, roles as roles_mod
from wordsworth.access_identity import Identity, Verifier
from wordsworth.api import create_app
from wordsworth.bootstrap import ensure_admin_role
from wordsworth.grants import PostgresGrantStore
from wordsworth.key_audit_pg import PostgresKeyLifecycleAudit
from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.models import AuditRecord
from wordsworth.pipeline import ingest, process
from wordsworth.pseudonymizer import Pseudonymizer

ISSUER = "https://iam.westerweel.work/realms/westerweel-reveal-groups"
JWKS = f"{ISSUER}/protocol/openid-connect/certs"
PII_EMAIL = "jan.jansen@haarlem.nl"
REFUSAL = {"detail": "grant not applicable"}


def _app(session_factory, key, key_provider=None):
    verifier = Verifier.oidc(ISSUER, "wordsworth", jwks_url=JWKS)
    app = create_app(session_factory=session_factory, grant_store_factory=PostgresGrantStore,
                     key_provider=key_provider or InMemoryKeyProvider(),
                     access_verifier=verifier)
    for m in app.user_middleware:
        if m.cls.__name__ == "ApiKeyAuthMiddleware":
            m.kwargs["identity"] = Identity(verifier, fetch=lambda url: _jwks(key))
    return app, verifier


def _bearer(key, verifier, email, **claims) -> dict:
    token = _token(key, aud=["wordsworth"], iss=verifier.issuer,
                   exp=time.time() + 3600, email_verified=True, email=email,
                   **claims)
    return {"Authorization": f"Bearer {token}"}


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


def test_a_group_mapped_to_beheerder_does_not_open_an_unscoped_grant(
        session_factory):
    """The exact scenario the change forbids: a group on `beheerder`, an
    unscoped grant naming someone else, and no new access through either."""
    key = _key()
    with session_factory() as s:
        ensure_admin_role(s)
        group_roles.map_role(s, "hr-afdeling", roles_mod.ADMIN, actor="mark",
                             audit=PostgresKeyLifecycleAudit(s))
        gs = PostgresGrantStore(s)
        grant = gs.issue("iemand-anders", [], actor="t", role=roles_mod.ADMIN)
        s.commit()
        grant_id = grant.grant_id

    app, verifier = _app(session_factory, key)
    c = TestClient(app, raise_server_exceptions=False)
    r = c.post("/documents/00000000-0000-0000-0000-000000000000/reveal",
              json={"grant_id": grant_id},
              headers=_bearer(key, verifier, "lid@gemeente.nl",
                              groups=["hr-afdeling"]))
    assert r.status_code == 403
    assert r.json() == REFUSAL


def test_a_group_mapped_to_a_role_with_no_personal_grant_cannot_reveal(
        session_factory, mem_store, mem_index, fake_embedder, born_digital_pii_pdf):
    key = _key()
    kp, doc_id = _document(session_factory, mem_store, mem_index, fake_embedder,
                          born_digital_pii_pdf)
    with session_factory() as s:
        roles_mod.create(s, "HR", ["EMAIL"], actor="mark",
                         audit=PostgresKeyLifecycleAudit(s))
        group_roles.map_role(s, "hr-afdeling", "HR", actor="mark",
                             audit=PostgresKeyLifecycleAudit(s))
        gs = PostgresGrantStore(s)
        grant = gs.issue("iemand-anders", [], actor="t", document_id=doc_id, role="HR")
        s.commit()
        grant_id = grant.grant_id

    app, verifier = _app(session_factory, key)
    c = TestClient(app, raise_server_exceptions=False)
    r = c.post(f"/documents/{doc_id}/reveal", json={"grant_id": grant_id},
              headers=_bearer(key, verifier, "lid@gemeente.nl",
                              groups=["hr-afdeling"]))
    assert r.status_code == 403
    assert r.json() == REFUSAL


def test_the_same_caller_with_a_personal_grant_reveals_and_is_named_in_the_audit(
        session_factory, mem_store, mem_index, fake_embedder, born_digital_pii_pdf):
    key = _key()
    kp, doc_id = _document(session_factory, mem_store, mem_index, fake_embedder,
                          born_digital_pii_pdf)
    with session_factory() as s:
        roles_mod.create(s, "HR", ["EMAIL"], actor="mark",
                         audit=PostgresKeyLifecycleAudit(s))
        group_roles.map_role(s, "hr-afdeling", "HR", actor="mark",
                             audit=PostgresKeyLifecycleAudit(s))
        gs = PostgresGrantStore(s)
        grant = gs.issue("lid@gemeente.nl", [], actor="t", document_id=doc_id,
                        role="HR")
        s.commit()
        grant_id = grant.grant_id

    app, verifier = _app(session_factory, key, key_provider=kp)
    c = TestClient(app, raise_server_exceptions=False)
    r = c.post(f"/documents/{doc_id}/reveal",
              json={"grant_id": grant_id, "types": ["EMAIL"]},
              headers=_bearer(key, verifier, "lid@gemeente.nl",
                              groups=["hr-afdeling"]))
    assert r.status_code == 200, r.text
    assert PII_EMAIL in r.json()["revealed_text"]

    with session_factory() as s:
        payload = s.execute(
            select(AuditRecord.payload)
            .where(AuditRecord.document_id == doc_id,
                   AuditRecord.step == "deanonymize")
            .order_by(AuditRecord.seq.desc()).limit(1)).scalar_one()
    assert payload.get("actor") == "lid@gemeente.nl", (
        "de onthulling hoort de persoon te noemen, niet de groep")
    assert "hr-afdeling" not in str(payload)
