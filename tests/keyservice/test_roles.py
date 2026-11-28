"""design.md "Identity": the service's own role resolution (never a
fallback) and ``wordsworth-keyservice-init``'s admin role (mirrors
``wordsworth.bootstrap.ensure_admin_role``)."""
from __future__ import annotations

from wordsworth.keyservice import roles
from wordsworth.keyservice.lifecycle import verify_lifecycle_chain
from wordsworth.keyservice.models_access import Role
from wordsworth.pii_categories import known_types


def test_an_unknown_role_resolves_to_nothing(keyservice_session_factory):
    with keyservice_session_factory() as s:
        resolved = roles.resolve(s, "no-such-role")
    assert resolved.types == frozenset()
    assert resolved.reason == "unknown role"


def test_no_role_resolves_to_nothing(keyservice_session_factory):
    with keyservice_session_factory() as s:
        resolved = roles.resolve(s, None)
    assert resolved.types == frozenset()


def test_an_inactive_role_resolves_to_nothing_never_a_fallback(keyservice_session_factory):
    with keyservice_session_factory() as s:
        s.add(Role(name="afdeling", allowed_types=["PERSON"], active=False,
                   created_by="t"))
        s.commit()
        resolved = roles.resolve(s, "afdeling")
    assert resolved.types == frozenset()
    assert resolved.reason == "role inactive"


def test_an_active_role_resolves_to_its_types(keyservice_session_factory):
    with keyservice_session_factory() as s:
        s.add(Role(name="afdeling", allowed_types=["PERSON", "EMAIL"], active=True,
                   created_by="t"))
        s.commit()
        resolved = roles.resolve(s, "afdeling")
    assert resolved.types == frozenset({"PERSON", "EMAIL"})


def test_the_installation_creates_the_admin_role(keyservice_session_factory):
    with keyservice_session_factory() as s:
        message = roles.ensure_admin_role(s, actor="installation")
        s.commit()
        row = s.get(Role, s.query(Role).filter_by(name=roles.ADMIN).first().id)
    assert row is not None and row.active
    assert set(row.allowed_types) == set(known_types())
    assert row.created_by == "installation"
    assert "created" in message


def test_running_it_again_leaves_an_existing_role_alone(keyservice_session_factory):
    """A redeploy must never silently restore a role an operator narrowed
    or switched off -- that is the opposite of a breakglass."""
    with keyservice_session_factory() as s:
        roles.ensure_admin_role(s, actor="installation")
        existing = s.query(Role).filter_by(name=roles.ADMIN).first()
        existing.allowed_types = ["PERSON"]
        existing.active = False
        s.commit()

        message = roles.ensure_admin_role(s, actor="installation")
        s.commit()
        row = s.query(Role).filter_by(name=roles.ADMIN).first()
    assert row.allowed_types == ["PERSON"], "the install overwrote the role"
    assert row.active is False, "the install reset the breakglass"
    assert "already exists" in message


def test_creating_the_admin_role_appends_one_lifecycle_event_and_the_chain_verifies(
        keyservice_session_factory):
    with keyservice_session_factory() as s:
        roles.ensure_admin_role(s, actor="installation")
        s.commit()
        ok, bad = verify_lifecycle_chain(s)
    assert ok is True and bad is None
