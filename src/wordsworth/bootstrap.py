"""One-shot schema bootstrap: create tables + the append-only audit trigger.

Idempotent (``CREATE OR REPLACE`` / ``DROP ... IF EXISTS`` inside
``init_schema``). Run once before serving or ingesting (``wordsworth-init``).
Requires a DB role permitted to create functions and triggers.

Maakt ook de **beheerdersrol** aan, als die er nog niet is. Mark, 2026-09-17:
*"er is altijd 1 (super)admin bij het aanmaken/installeren van de app, die
bepaalt de RBAC."* Die eerste rol komt dus niet uit het rollenstelsel maar uit
de installatie — zoals een root-account niet door een gebruikersbeheerder wordt
aangemaakt. Dat maakt de bootstrap een expliciet moment in plaats van een gat.

Alleen als hij er nog niet is: een bestaande beheerdersrol wordt níet
overschreven. Anders zou elke uitrol een ingeperkte of uitgezette rol stilletjes
terugzetten op "alles", en dat is het tegenovergestelde van een breakglass.
"""
from __future__ import annotations

from . import roles
from .db import init_schema, make_engine, make_session_factory
from .pii_categories import known_types


def ensure_admin_role(session) -> str:
    """De beheerdersrol, aangemaakt bij de installatie als hij ontbreekt."""
    bestaand = roles.by_name(session, roles.ADMIN)
    if bestaand is not None:
        return (f"rol {roles.ADMIN!r} bestaat al "
                f"({len(bestaand.allowed_types)} types, "
                f"{'actief' if bestaand.active else 'UIT'}) — ongemoeid gelaten")
    roles.create(session, roles.ADMIN, known_types(), actor="installatie")
    return f"rol {roles.ADMIN!r} aangemaakt met alle {len(known_types())} types"


def main() -> int:
    engine = make_engine()
    init_schema(engine)
    print("schema ready")
    maak = make_session_factory(engine)
    with maak() as session:
        print(ensure_admin_role(session))
        session.commit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
