# SPDX-License-Identifier: MIT
"""A group-held role never authorises a reveal (keycloak-groups-to-roles).

`grants.authorize` takes no group and no held-role — being in a group mapped
to a role makes a caller the recipient of no grant, and the function's
signature proves it structurally: there is nothing to pass it. This drives
the spec's three reveal scenarios through the one function that decides."""
from __future__ import annotations

import inspect
import uuid
from datetime import datetime, timezone

from wordsworth.grants import ACTIVE, Grant, authorize

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
DOC = uuid.uuid4()


def _resolver(types):
    return lambda name: types if name == "beheerder" else set()


def _grant(recipient, role="beheerder"):
    return Grant(grant_id=str(uuid.uuid4()), recipient=recipient, allowed_types=[],
                document_id=None, status=ACTIVE, created_at=NOW, revoked_at=None,
                expires_at=None, actor="mark", role=role)


def test_someone_elses_grant_naming_the_role_is_refused():
    """A caller whose group maps to `beheerder` presents an unscoped grant
    naming `beheerder` that was issued to someone else -- 403, no text."""
    grant = _grant(recipient="een-ander")
    assert authorize(grant, DOC, {"PERSON"}, NOW, caller="ict-caller",
                     auth_enabled=True, allow_global=True,
                     resolve_role=_resolver({"PERSON"}),
                     global_roles={"beheerder"}) == set()


def test_a_group_role_without_a_personal_grant_reveals_nothing():
    """No grant at all names the caller -- group membership itself carries no
    types, so there is nothing for `authorize` to grant."""
    assert authorize(_grant(recipient="een-ander"), DOC, {"PERSON"}, NOW,
                     caller="ict-caller", auth_enabled=True) == set()


def test_a_personal_grant_still_works_and_names_the_person():
    """The same caller, now the grant's recipient: the reveal proceeds exactly
    as for any recipient -- `authorize` never looked at a group either way."""
    grant = _grant(recipient="ict-caller")
    assert authorize(grant, DOC, {"PERSON"}, NOW, caller="ict-caller",
                     auth_enabled=True, allow_global=True,
                     resolve_role=_resolver({"PERSON"}),
                     global_roles={"beheerder"}) == {"PERSON"}


def test_authorize_takes_no_group_or_held_role_parameter():
    """Structural proof: a group-held role has no parameter through which it
    could ever reach this decision."""
    params = set(inspect.signature(authorize).parameters)
    assert "groups" not in params and "held_roles" not in params
