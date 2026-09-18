# SPDX-License-Identifier: MIT
"""What goes quiet when callers become people (access-identity).

A grant names who may reveal, and the caller must BE that recipient. Today a
recipient is a key label — `console`, `cli`. The moment callers are identities,
nobody is called `console` any more and every grant issued to a label authorises
nobody.

They do not become dangerous; they become inert. And an inert grant that still
reads as "active" is a lie in the table. The recipient binding taught this the
expensive way: four grants went quiet in August and it was noticed afterwards, by
looking.

So this reports them BEFORE the switch. It changes nothing. Moving an
authorisation from a shared key to a person is a judgement about who should hold
it, and that is exactly the decision a machine should not make on its own.
"""
from __future__ import annotations

import argparse

from sqlalchemy import select

from .db import make_engine, make_session_factory
from .grants import ACTIVE
from .models import GrantRecord


def at_risk(session, labels: set[str]) -> list[dict]:
    """Active grants whose recipient is a key label rather than an identity."""
    rows = session.execute(
        select(GrantRecord).where(GrantRecord.status == ACTIVE)).scalars()
    out = []
    for g in rows:
        # An identity is an email address. Anything else is a label, and a label
        # is what stops working.
        if "@" in g.recipient:
            continue
        out.append({"grant_id": g.grant_id, "recipient": g.recipient,
                    "types": sorted(g.allowed_types or []),
                    "known_label": g.recipient in labels,
                    "scope": "dit document" if g.document_id else "alle documenten"})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="wordsworth-access-preflight",
        description="Report grants that go inert once callers are identities")
    ap.parse_args(argv)

    from .config import settings

    labels = set(settings.api_keys.values())
    with make_session_factory(make_engine())() as session:
        found = at_risk(session, labels)
    if not found:
        print("geen actieve grants op een sleutellabel — omschakelen breekt niets")
        return 0
    print(f"{len(found)} actieve grant(s) worden inert zodra bellers identiteiten "
          f"zijn:\n")
    for g in found:
        merk = "" if g["known_label"] else "  (label bestaat niet meer)"
        print(f"  {g['recipient']:<20} {g['grant_id'][:8]}  "
              f"{', '.join(g['types'])}  [{g['scope']}]{merk}")
    print("\nZe onthullen daarna niets. Opnieuw uitgeven op een identiteit is een\n"
          "keuze van de beheerder; dit commando verandert niets.")
    return 0


if __name__ == "__main__":     # pragma: no cover
    raise SystemExit(main())
