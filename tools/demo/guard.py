# SPDX-License-Identifier: MIT
"""What serve_local refuses before it touches a database.

The demo creates a schema, seeds keys wrapped under a public test KEK, and with
--reset drops every table. So it runs only on a database whose name says it is
a demo or test database, and that name is checked twice: in the URL, and as
the server reports it once connected -- a URL can name one database and
connect to another (`?dbname=`, a service file, PG* variables).
"""
from __future__ import annotations

import os

from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url

ALLOWED = ("wordsworth_demo", "wordsworth_test")
_ALLOWED_TEXT = " or ".join(p + "*" for p in ALLOWED)


class Refused(SystemExit):
    def __init__(self, why: str):
        super().__init__(f"serve_local: {why}")


def check_url(url: str) -> str:
    """The database name the URL names, after refusing what this tool must not touch."""
    u = make_url(url)
    if u.drivername != "postgresql+psycopg":
        raise Refused(f"use a postgresql+psycopg:// URL, not {u.drivername}://")
    if u.query:
        # `?dbname=` (and its kin) override the path, so the name checked below
        # would not be the database connected to.
        raise Refused(f"no query parameters in the database URL: {sorted(u.query)}")
    return check_database(u.database or "")


def check_database(name: str) -> str:
    if not name.startswith(ALLOWED):
        raise Refused(f"the demo only runs on a database named {_ALLOWED_TEXT}, "
                      f"not {name!r}")
    return name


def connected_name(engine) -> str:
    """The database the server says this connection is in."""
    with engine.connect() as conn:
        return conn.execute(text("SELECT current_database()")).scalar_one()


def refuse_if_held(session_factory, name: str) -> None:
    """A database seeded by an earlier run lost its index and its PDFs with that
    process; serving it would show empty searches and missing PDFs, unexplained."""
    from wordsworth.models import Document

    with session_factory() as s:
        held = s.execute(select(func.count()).select_from(Document)).scalar_one()
    if held:
        raise Refused(f"{name!r} already holds {held} documents from an earlier run; "
                      "their index and PDFs died with that process. Pass --reset "
                      "or use an empty database.")


def clear_environment() -> list[str]:
    """Remove every WORDSWORTH_* variable from this process; returns their names.

    `create_app` reads its settings from the environment (identity provider,
    global grants, detection lists, rate limits, ...). A variable left over from
    another shell would change what the demo shows without saying so."""
    names = sorted(k for k in os.environ if k.startswith("WORDSWORTH_"))
    for k in names:
        del os.environ[k]
    return names
