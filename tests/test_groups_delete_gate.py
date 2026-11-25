# SPDX-License-Identifier: MIT
"""keycloak-groups-to-roles, tasks 3 and 5: a group-held `beheerder` opens the
delete gate exactly like a grant-held one -- while the group is on the
caller's verified assertion AND the role is active -- and an API key or the
console cookie carries no groups, even when a valid assertion with groups
rides along on the same request."""
from __future__ import annotations

import time

from fastapi.testclient import TestClient

from test_access_identity import _jwks, _key, _token
from wordsworth import group_roles, roles
from wordsworth.access_identity import Identity, Verifier
from wordsworth.api import create_app
from wordsworth.audit import current_state
from wordsworth.auth import CONSOLE_COOKIE
from wordsworth.bootstrap import ensure_admin_role
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.pipeline import register
from wordsworth.search_index import InMemoryIndex
from wordsworth.states import State

ISSUER = "https://iam.westerweel.work/realms/westerweel-groups"
JWKS = f"{ISSUER}/protocol/openid-connect/certs"
KEY_FILE = "documents/" + "9f" * 32


def _seed(session_factory, *, group="hr-afdeling", role=roles.ADMIN, active=True):
    with session_factory() as s:
        ensure_admin_role(s)
        if role != roles.ADMIN:
            roles.create(s, role, [], actor="t", audit=_stroom(s))
        if not active:
            roles.deactivate(s, role, actor="mark", reason="breakglass",
                             audit=_stroom(s))
        group_roles.map_role(s, group, role, actor="mark", audit=_stroom(s))
        doc = register(s, KEY_FILE)
        s.commit()
        return doc.id


def _stroom(session):
    from wordsworth.key_audit_pg import PostgresKeyLifecycleAudit

    return PostgresKeyLifecycleAudit(session)


def _app(session_factory, key):
    verifier = Verifier.oidc(ISSUER, "wordsworth", jwks_url=JWKS)
    app = create_app(session_factory=session_factory, store=InMemoryObjectStore(),
                     search_index=InMemoryIndex(), access_verifier=verifier,
                     api_keys={"k-nobody": "nobody-caller"})
    for m in app.user_middleware:
        if m.cls.__name__ == "ApiKeyAuthMiddleware":
            m.kwargs["identity"] = Identity(verifier, fetch=lambda url: _jwks(key))
    return app, verifier


def _bearer(key, verifier, **claims) -> dict:
    token = _token(key, aud=["wordsworth"], iss=verifier.issuer,
                   exp=time.time() + 3600, email_verified=True, **claims)
    return {"Authorization": f"Bearer {token}"}


def test_a_group_held_beheerder_deletes_via_the_assertion(session_factory):
    key = _key()
    doc_id = _seed(session_factory)
    app, verifier = _app(session_factory, key)
    c = TestClient(app, raise_server_exceptions=False)
    r = c.delete(f"/documents/{doc_id}",
                headers=_bearer(key, verifier, groups=["hr-afdeling"],
                                email="lid@gemeente.nl"))
    assert r.status_code == 200
    with session_factory() as s:
        assert current_state(s, doc_id) == State.DELETED
        from sqlalchemy import select

        from wordsworth.models import AuditRecord

        payload = s.execute(
            select(AuditRecord.payload)
            .where(AuditRecord.document_id == doc_id,
                   AuditRecord.step == "delete")).scalar_one()
        # de persoon staat erin, nooit de groep (keycloak-groups-to-roles, taak 7).
        assert payload["actor"] == "lid@gemeente.nl"
        assert "hr-afdeling" not in str(payload)


def test_the_group_leaving_the_assertion_refuses_the_delete(session_factory):
    key = _key()
    doc_id = _seed(session_factory)
    app, verifier = _app(session_factory, key)
    c = TestClient(app, raise_server_exceptions=False)
    r = c.delete(f"/documents/{doc_id}", headers=_bearer(key, verifier, groups=[]))
    assert r.status_code == 403
    with session_factory() as s:
        assert current_state(s, doc_id) == State.REGISTERED


def test_a_switched_off_role_refuses_a_group_held_delete(session_factory):
    key = _key()
    doc_id = _seed(session_factory, active=False)
    app, verifier = _app(session_factory, key)
    c = TestClient(app, raise_server_exceptions=False)
    r = c.delete(f"/documents/{doc_id}",
                headers=_bearer(key, verifier, groups=["hr-afdeling"]))
    assert r.status_code == 403
    with session_factory() as s:
        assert current_state(s, doc_id) == State.REGISTERED


def test_an_api_key_presented_alongside_a_group_bearing_assertion_carries_no_groups(
        session_factory):
    """A sent credential beats one that rides along: the key names a label,
    and a label has no groups -- "no groups; use a personal grant or label"."""
    key = _key()
    doc_id = _seed(session_factory)
    app, verifier = _app(session_factory, key)
    c = TestClient(app, raise_server_exceptions=False)
    headers = _bearer(key, verifier, groups=["hr-afdeling"])
    headers["X-API-Key"] = "k-nobody"
    r = c.delete(f"/documents/{doc_id}", headers=headers)
    assert r.status_code == 403
    with session_factory() as s:
        assert current_state(s, doc_id) == State.REGISTERED


def test_the_console_cookie_carries_no_groups_either(session_factory):
    key = _key()
    doc_id = _seed(session_factory)
    app, verifier = _app(session_factory, key)
    c = TestClient(app, raise_server_exceptions=False)
    c.cookies.set(CONSOLE_COOKIE, "k-nobody")
    r = c.delete(f"/documents/{doc_id}", headers=_bearer(key, verifier,
                                                         groups=["hr-afdeling"]))
    assert r.status_code == 403
    with session_factory() as s:
        assert current_state(s, doc_id) == State.REGISTERED
