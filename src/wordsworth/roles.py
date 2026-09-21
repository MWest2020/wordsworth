# SPDX-License-Identifier: MIT
"""Rollen: een naam plus de PII-types die eronder zichtbaar mogen zijn (rollen).

Een rol is **geen sjabloon maar een entiteit.** Het verschil zit in wat er
gebeurt als je hem uitzet.

Bij een sjabloon zou een rol toekennen betekenen: de types kopiëren naar een
grant. Die grant leeft daarna zijn eigen leven. Een rol uitzetten is dan een
opruimactie — elke uitgegeven grant terugvinden en intrekken, met een
tijdvenster erin, precies op het moment dat je er geen wilt. En een rol inperken
verandert niets aan wat er al is uitgegeven: je denkt dat je iets hebt
dichtgezet en dat is niet zo.

Als entiteit lost `authorize()` de rol op op het moment dat hij beslist. Een rol
uitzetten werkt dan onmiddellijk en exact, zonder dat er één grant verandert.

**De rol levert de types, de grant levert de scope.** Mark, 2026-09-19: *"ik
maak een rol aan en selecteer welke PII's mogen, per document of globaal?"* — ja,
en die twee horen op verschillende plekken. Dezelfde rol kan aan de een gegeven
worden voor één document en aan de ander voor alles; zat de scope in de rol, dan
waren dat twee rollen die morgen uit elkaar lopen.

Wat hier NIET woont: wie iemand is. Dat komt uit de aanmelding (Cloudflare
Access, en ooit iets als Keycloak). Deze module kent alleen namen die van daar
komen — zodat de dag dat rollidmaatschap ergens anders vandaan komt, alleen dát
punt verandert en niet de beslissing.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import Role

#: De rol die alles ziet. Bestaat als gewone rol en niet als pad langs
#: `authorize()`: een beheerder die langs de autorisatie mag, is de tweede deur
#: die dit project nergens heeft — en het is de deur die het meest gebruikt
#: wordt en het minst bekeken.
ADMIN = "beheerder"


class RoleError(ValueError):
    """Een rol-handeling die niet kan."""


@dataclass(frozen=True)
class Resolved:
    """Wat een rol op dit moment toestaat, plus waaróm dat zo is.

    De reden staat erbij omdat een lege verzameling twee heel verschillende
    dingen kan betekenen — de rol bestaat niet, of hij is uitgezet — en het
    auditspoor die twee uit elkaar moet kunnen houden.
    """

    types: frozenset[str]
    reason: str


def create(session: Session, name: str, allowed_types, actor: str,
           audit=None) -> Role:
    """Maak een rol aan met de types die eronder zichtbaar mogen zijn."""
    name = (name or "").strip()
    if not name:
        raise RoleError("een rol heeft een naam nodig")
    types = normalise(allowed_types)
    try:
        with session.begin_nested():
            role = Role(name=name, allowed_types=sorted(types), active=True,
                        created_by=actor)
            session.add(role)
            session.flush()
        _noteer(audit, role, "created", actor, None)
        return role
    except IntegrityError:
        raise RoleError(f"rol {name!r} bestaat al")


def normalise(allowed_types) -> set[str]:
    """Types in de vorm waarin de rest van het systeem ze kent: hoofdletters.

    Op één plek, want een rol die `person` opslaat en een grant die `PERSON`
    vergelijkt is een autorisatiefout die er als een typefout uitziet.
    """
    return {t.strip().upper() for t in (allowed_types or ()) if t and t.strip()}


def by_name(session: Session, name: str) -> Role | None:
    return session.execute(
        select(Role).where(Role.name == name)).scalars().first()


def listing(session: Session) -> list[Role]:
    return list(session.execute(select(Role).order_by(Role.name)).scalars())


def set_types(session: Session, name: str, allowed_types, actor: str,
              audit=None) -> Role:
    """Verander wat deze rol toestaat.

    Werkt onmiddellijk door in elke grant die de rol noemt — dat is het punt.
    Wat er eerder onthuld is verandert niet: dat is gebeurd en staat in het
    spoor. Een scherm dat een ingeperkte rol toont zonder dat erbij te zeggen,
    laat "die gegevens zijn nooit gezien" lezen waar "vanaf nu niet meer" staat.
    """
    role = _must(session, name)
    role.allowed_types = sorted(normalise(allowed_types))
    session.flush()
    _noteer(audit, role, "types", actor, None)
    return role


def deactivate(session: Session, name: str, actor: str, reason: str,
               audit=None) -> Role:
    """Breakglass: zet een rol uit.

    Een reden is verplicht. Een noodrem zonder reden is een schakelaar waarvan
    niemand later kan navertellen waarom hij overging, en dit is precies het
    moment waarop dat uitmaakt.

    Er verandert geen enkele grant. Dat is het bewijs dat de rol een entiteit is
    en geen sjabloon: één regel om, en elke grant die hem noemt autoriseert
    niets meer.
    """
    if not (reason or "").strip():
        raise RoleError("uitzetten vraagt een reden")
    role = _must(session, name)
    role.active = False
    session.flush()
    _noteer(audit, role, "deactivated", actor, reason)
    return role


def activate(session: Session, name: str, actor: str, reason: str,
             audit=None) -> Role:
    """En weer aan. Ook met een reden: terugzetten is net zo goed een besluit."""
    if not (reason or "").strip():
        raise RoleError("aanzetten vraagt een reden")
    role = _must(session, name)
    role.active = True
    session.flush()
    _noteer(audit, role, "activated", actor, reason)
    return role


def resolve(session: Session, name: str | None) -> Resolved:
    """Wat deze rol op dit moment toestaat.

    Een onbekende of uitgezette rol levert een lege verzameling en **nooit** een
    terugval: niet op de typelijst van de grant, niet op een vorige versie van
    de rol, niet op een standaard. Een terugval zou van uitzetten een suggestie
    maken.
    """
    if not name:
        return Resolved(frozenset(), "geen rol")
    role = by_name(session, name)
    if role is None:
        return Resolved(frozenset(), "onbekende rol")
    if not role.active:
        return Resolved(frozenset(), "rol staat uit")
    return Resolved(frozenset(role.allowed_types or ()), "rol actief")


def _noteer(audit, role: Role, change: str, actor: str, reason: str | None) -> None:
    """Schrijf de wijziging naar het sleutel-levensloopspoor.

    Niet in de document-hashketen: die is de toestandsmachine van één document,
    en een rol raakt er duizend. Een record per document zou de keten
    volschrijven met duizend kopieën van hetzelfde feit; één record zonder
    document past er niet in. Rollen staan daarom waar grants en
    sleutelrotaties ook staan — globale autorisatiefeiten zonder document, in
    een eigen append-only stroom.

    `audit=None` betekent: geen spoor. Dat is geen stille uitzondering maar de
    testmodus; elke aanroeper uit de API geeft er een mee.
    """
    if audit is None:
        return
    audit.role_changed(role=role.name, change=change,
                       allowed_types=list(role.allowed_types),
                       active=role.active, actor=actor, reason=reason)


def _must(session: Session, name: str) -> Role:
    role = by_name(session, name)
    if role is None:
        raise RoleError(f"onbekende rol {name!r}")
    return role
