# SPDX-License-Identifier: MIT
"""De beheerdersrol komt uit de installatie (rollen).

Mark, 2026-09-17: er is altijd één (super)admin bij het installeren, en die
bepaalt de RBAC. Die eerste rol komt dus niet uit het rollenstelsel zelf —
zoals een root-account niet door een gebruikersbeheerder wordt aangemaakt.
"""
from __future__ import annotations

from wordsworth import roles
from wordsworth.key_audit_pg import PostgresKeyLifecycleAudit as _Stroom
from wordsworth.bootstrap import ensure_admin_role
from wordsworth.pii_categories import known_types


def test_the_installation_creates_the_admin_role(session_factory):
    with session_factory() as s:
        melding = ensure_admin_role(s)
        s.commit()
        rol = roles.by_name(s, roles.ADMIN)
        assert rol is not None and rol.active
        assert set(rol.allowed_types) == set(known_types())
        assert rol.created_by == "installatie"
        assert "aangemaakt" in melding


def test_running_it_again_leaves_the_role_alone(session_factory):
    """Zou elke uitrol de rol terugzetten op "alles", dan is een ingeperkte of
    uitgezette beheerdersrol één deploy lang geldig. Dat is het
    tegenovergestelde van een breakglass."""
    with session_factory() as s:
        ensure_admin_role(s)
        roles.set_types(s, roles.ADMIN, ["PERSON"], actor="mark", audit=_Stroom(s))
        roles.deactivate(s, roles.ADMIN, actor="mark", reason="lek", audit=_Stroom(s))
        s.commit()

        melding = ensure_admin_role(s)
        s.commit()
        rol = roles.by_name(s, roles.ADMIN)
        assert rol.allowed_types == ["PERSON"], "de installatie overschreef de rol"
        assert rol.active is False, "de installatie zette de breakglass terug"
        assert "bestaat al" in melding
