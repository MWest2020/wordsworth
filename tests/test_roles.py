# SPDX-License-Identifier: MIT
"""Rollen (rollen): een naam plus types, opgelost bij het beslissen.

Waarom deze vorm en geen sjabloon staat in `roles.py`. Deze tests bewijzen het
verschil: een rol uitzetten of inperken werkt onmiddellijk, **zonder dat er één
grant verandert**. Bij een sjabloon zou dat een opruimactie met een tijdvenster
zijn, precies op het moment dat je er geen wilt.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from wordsworth import roles
from wordsworth.grants import InMemoryGrantStore, authorize
from wordsworth.models import Role

NU = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)


def _resolver(session):
    return lambda naam: roles.resolve(session, naam).types


def _grant_met_rol(gs, rol, doc_id=None):
    # Een grant die een rol noemt draagt geen eigen typelijst: twee bronnen voor
    # één antwoord is precies hoe autorisatiefouten ontstaan.
    return gs.issue("mark@westerweel.work", [], actor="installatie",
                    document_id=doc_id, role=rol)


def test_a_role_supplies_the_types(session_factory):
    with session_factory() as s:
        roles.create(s, "hr", ["person", "email"], actor="mark")
        s.flush()
        gs = InMemoryGrantStore()
        g = _grant_met_rol(gs, "hr", doc_id=None)
        assert authorize(g, None, ["PERSON", "BSN"], NU, allow_global=True,
                         resolve_role=_resolver(s)) == {"PERSON"}


def test_switching_a_role_off_closes_every_grant_that_names_it(session_factory):
    """Het hele punt van deze vorm. Eén regel om, en geen enkele grant is
    aangeraakt."""
    with session_factory() as s:
        roles.create(s, "hr", ["PERSON"], actor="mark")
        s.flush()
        gs = InMemoryGrantStore()
        g = _grant_met_rol(gs, "hr")
        voor = (g.status, list(g.allowed_types), g.role)
        assert authorize(g, None, ["PERSON"], NU, allow_global=True,
                         resolve_role=_resolver(s)) == {"PERSON"}

        roles.deactivate(s, "hr", actor="mark", reason="lek gemeld")
        s.flush()
        assert authorize(g, None, ["PERSON"], NU, allow_global=True,
                         resolve_role=_resolver(s)) == set()
        assert (g.status, list(g.allowed_types), g.role) == voor, (
            "er is een grant veranderd; dan is dit een sjabloon en geen rol")


def test_narrowing_a_role_narrows_its_grants_at_once(session_factory):
    with session_factory() as s:
        roles.create(s, "hr", ["PERSON", "EMAIL"], actor="mark")
        s.flush()
        gs = InMemoryGrantStore()
        g = _grant_met_rol(gs, "hr")
        assert authorize(g, None, ["EMAIL"], NU, allow_global=True,
                         resolve_role=_resolver(s)) == {"EMAIL"}
        roles.set_types(s, "hr", ["PERSON"], actor="mark")
        s.flush()
        assert authorize(g, None, ["EMAIL"], NU, allow_global=True,
                         resolve_role=_resolver(s)) == set()


def test_a_grant_with_its_own_types_is_untouched(session_factory):
    """Bestaande grants veranderen niet. Beide vormen bestaan naast elkaar."""
    with session_factory() as s:
        gs = InMemoryGrantStore()
        g = gs.issue("iemand", ["EMAIL"], actor="mark")
        assert authorize(g, None, ["EMAIL"], NU, allow_global=True,
                         resolve_role=_resolver(s)) == {"EMAIL"}


def test_an_unknown_role_authorises_nothing(session_factory):
    with session_factory() as s:
        gs = InMemoryGrantStore()
        g = _grant_met_rol(gs, "bestaat-niet")
        assert authorize(g, None, ["PERSON"], NU, allow_global=True,
                         resolve_role=_resolver(s)) == set()


def test_without_a_resolver_a_role_grant_authorises_nothing(session_factory):
    """Fail-closed. Een aanroeper die de rol niet kan opzoeken weet niet wat hij
    toestaat, en dan is "niets" het enige veilige antwoord. Een terugval op
    `grant.allowed_types` zou van een uitgezette rol een suggestie maken."""
    gs = InMemoryGrantStore()
    g = gs.issue("iemand", ["PERSON"], actor="mark", role="hr")
    assert authorize(g, None, ["PERSON"], NU, allow_global=True) == set()


def test_a_role_never_falls_back_to_the_grants_own_list(session_factory):
    """Zelfs als de grant per ongeluk allebei draagt, wint de rol. Anders is er
    een pad waarlangs een uitgezette rol tóch types oplevert."""
    with session_factory() as s:
        roles.create(s, "hr", ["PERSON"], actor="mark")
        roles.deactivate(s, "hr", actor="mark", reason="test")
        s.flush()
        gs = InMemoryGrantStore()
        g = gs.issue("iemand", ["BSN", "EMAIL"], actor="mark", role="hr")
        assert authorize(g, None, ["BSN", "EMAIL"], NU, allow_global=True,
                         resolve_role=_resolver(s)) == set()


def test_switching_off_needs_a_reason(session_factory):
    """Een noodrem zonder reden is een schakelaar waarvan niemand later kan
    navertellen waarom hij overging."""
    with session_factory() as s:
        roles.create(s, "hr", ["PERSON"], actor="mark")
        s.flush()
        with pytest.raises(roles.RoleError):
            roles.deactivate(s, "hr", actor="mark", reason="  ")
        assert roles.by_name(s, "hr").active is True


def test_a_role_comes_back_on(session_factory):
    with session_factory() as s:
        roles.create(s, "hr", ["PERSON"], actor="mark")
        roles.deactivate(s, "hr", actor="mark", reason="lek")
        s.flush()
        roles.activate(s, "hr", actor="mark", reason="lek gedicht")
        s.flush()
        assert roles.resolve(s, "hr").types == {"PERSON"}


def test_the_empty_set_says_why(session_factory):
    """Een lege verzameling betekent twee heel verschillende dingen, en het
    spoor moet die uit elkaar kunnen houden."""
    with session_factory() as s:
        roles.create(s, "hr", ["PERSON"], actor="mark")
        s.flush()
        assert roles.resolve(s, "weg").reason == "onbekende rol"
        roles.deactivate(s, "hr", actor="mark", reason="x")
        s.flush()
        assert roles.resolve(s, "hr").reason == "rol staat uit"
        assert roles.resolve(s, None).reason == "geen rol"


def test_types_are_stored_upper_case(session_factory):
    """Een rol die `person` bewaart naast een grant die `PERSON` vergelijkt is
    een autorisatiefout die eruitziet als een typefout."""
    with session_factory() as s:
        r = roles.create(s, "hr", [" person ", "Email", ""], actor="mark")
        s.flush()
        assert r.allowed_types == ["EMAIL", "PERSON"]


def test_a_duplicate_role_is_refused(session_factory):
    with session_factory() as s:
        roles.create(s, "hr", ["PERSON"], actor="mark")
        s.flush()
        with pytest.raises(roles.RoleError):
            roles.create(s, "hr", ["BSN"], actor="mark")
        s.flush()
        assert len([r for r in roles.listing(s) if r.name == "hr"]) == 1


def test_an_unscoped_grant_is_allowed_on_the_name_of_a_role(session_factory):
    """"Alles zien" is wat een beheerder doet. De twee alternatieven waren: de
    vlag omzetten (en dan mag élke ongescopete grant weer alles, voor iedereen)
    of per document een grant (791 stuks). De uitzondering draagt nu een naam."""
    with session_factory() as s:
        roles.create(s, roles.ADMIN, ["PERSON", "BSN"], actor="installatie")
        roles.create(s, "hr", ["PERSON"], actor="mark")
        s.flush()
        gs = InMemoryGrantStore()
        van_beheerder = _grant_met_rol(gs, roles.ADMIN)
        van_hr = _grant_met_rol(gs, "hr")
        r = _resolver(s)
        assert authorize(van_beheerder, None, ["PERSON"], NU, allow_global=False,
                         resolve_role=r, global_roles={roles.ADMIN}) == {"PERSON"}
        assert authorize(van_hr, None, ["PERSON"], NU, allow_global=False,
                         resolve_role=r, global_roles={roles.ADMIN}) == set()


def test_the_admin_role_is_not_a_bypass(session_factory):
    """Een beheerder gaat langs dezelfde autorisatie. Uitzetten werkt ook op
    hem — anders is de beheerdersrol de tweede deur die dit project nergens
    heeft, en het is de deur die het meest gebruikt wordt en het minst bekeken."""
    with session_factory() as s:
        roles.create(s, roles.ADMIN, ["PERSON"], actor="installatie")
        s.flush()
        gs = InMemoryGrantStore()
        g = _grant_met_rol(gs, roles.ADMIN)
        roles.deactivate(s, roles.ADMIN, actor="mark", reason="breakglass")
        s.flush()
        assert authorize(g, None, ["PERSON"], NU, allow_global=False,
                         resolve_role=_resolver(s),
                         global_roles={roles.ADMIN}) == set()


def test_a_role_grant_still_obeys_its_document_scope(session_factory):
    """De rol levert de types, de grant levert de scope. Die twee mogen elkaar
    niet overschrijven."""
    from uuid import uuid4

    with session_factory() as s:
        roles.create(s, "hr", ["PERSON"], actor="mark")
        s.flush()
        dit, dat = uuid4(), uuid4()
        gs = InMemoryGrantStore()
        g = _grant_met_rol(gs, "hr", doc_id=dit)
        r = _resolver(s)
        assert authorize(g, dit, ["PERSON"], NU, resolve_role=r) == {"PERSON"}
        assert authorize(g, dat, ["PERSON"], NU, resolve_role=r) == set()


def test_a_role_survives_a_round_trip_through_postgres(session_factory):
    """De rol moet de opslag overleven, anders lost `authorize()` straks in
    productie niets op en valt hij stil terug op een lege lijst."""
    from wordsworth.grants import PostgresGrantStore

    with session_factory() as s:
        roles.create(s, "hr", ["PERSON"], actor="mark")
        gs = PostgresGrantStore(s)
        uitgegeven = gs.issue("iemand", [], actor="mark", role="hr")
        s.commit()
        opnieuw = PostgresGrantStore(s).get(uitgegeven.grant_id)
        assert opnieuw.role == "hr"
        assert authorize(opnieuw, None, ["PERSON"], NU, allow_global=True,
                         resolve_role=_resolver(s)) == {"PERSON"}


def test_a_role_is_a_row_not_a_copy(session_factory):
    """Bewijs dat de types niet bij uitgifte zijn overgeschreven."""
    with session_factory() as s:
        roles.create(s, "hr", ["PERSON"], actor="mark")
        s.flush()
        gs = InMemoryGrantStore()
        g = _grant_met_rol(gs, "hr")
        assert g.allowed_types == [], "de grant heeft de types gekopieerd"
        assert s.get(Role, roles.by_name(s, "hr").id).allowed_types == ["PERSON"]
