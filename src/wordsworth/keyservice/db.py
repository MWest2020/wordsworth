"""Engine/session factory, schema init over ``KeyServiceBase.metadata``, and
the refuse-to-start check (design.md "Refuse to start"). No migrations: the
service database holds no data until the cutover, so a schema change until
then is made by dropping and recreating (design.md "Schema")."""
from __future__ import annotations

import logging
import os
import time

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from wordsworth.db_migrations import _FORBID_FUNCTION_SQL

from .config import settings
from .models import KeyServiceBase
from . import models_access  # noqa: F401 -- registers its tables on KeyServiceBase.metadata

log = logging.getLogger(__name__)

#: 55P03 = ``lock_timeout`` expired; 40P01 = chosen as a deadlock victim --
#: both mean a retry is safe, the same set wordsworth's ``db.py`` uses.
_LOCK_CONFLICTS = {"55P03", "40P01"}

#: (trigger, table) pairs the service's init makes append-only, using the
#: same trigger function (``wordsworth_forbid_mutation``) as wordsworth's own.
_APPEND_ONLY = [
    ("access_audit_no_mutation", "access_audit"),
    ("key_lifecycle_no_mutation", "key_lifecycle_events"),
]

#: Tables that exist only in wordsworth's database (``wordsworth.models``).
#: Their presence means ``KEYSERVICE_DATABASE_URL`` points at wordsworth's
#: database however the rest of the environment is configured -- rule 3
#: catches the real thing, not merely a matching setting.
_WORDSWORTH_ONLY_TABLES = ("audit_records", "document_texts")


class RefuseToStart(Exception):
    """Raised by ``check_refuse_to_start``. Callers (``serve.py``'s startup
    event, ``bootstrap.main``) let it propagate so the process exits
    non-zero -- never a warning."""


def _is_lock_conflict(exc: OperationalError) -> bool:
    return getattr(getattr(exc, "orig", None), "sqlstate", None) in _LOCK_CONFLICTS


def check_refuse_to_start(database_url: str) -> None:
    """The three rules, in order, over ``database_url`` -- never over the
    current ``settings.database_url``, so a caller can exercise one rule in
    isolation. Rule 2 reads ``WORDSWORTH_DATABASE_URL`` straight from
    ``os.environ`` (design.md "Settings"): never through ``wordsworth.config``,
    and used for nothing but this comparison."""
    if not database_url:
        raise RefuseToStart("rule 1: KEYSERVICE_DATABASE_URL is unset or empty")

    wordsworth_url = os.environ.get("WORDSWORTH_DATABASE_URL", "")
    if wordsworth_url:
        a, b = make_url(database_url), make_url(wordsworth_url)
        if (a.host, a.port, a.database) == (b.host, b.port, b.database):
            raise RefuseToStart(
                "rule 2: KEYSERVICE_DATABASE_URL names the same database as "
                "WORDSWORTH_DATABASE_URL")

    names_sql = ", ".join(f"'{t}'" for t in _WORDSWORTH_ONLY_TABLES)
    engine = create_engine(database_url, future=True)
    try:
        with engine.connect() as conn:
            found = sorted(conn.execute(text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = current_schema() "
                f"AND table_name IN ({names_sql})"
            )).scalars().all())
    finally:
        engine.dispose()
    if found:
        raise RefuseToStart(f"rule 3: database already holds wordsworth tables {found}")


def make_engine(url: str | None = None) -> Engine:
    return create_engine(
        url or settings.database_url,
        future=True,
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args={"options": "-c timezone=utc"},
    )


def _missing_triggers(conn) -> list[str]:
    trigs = {tuple(r) for r in conn.execute(text(
        "SELECT tgname, tgrelid::regclass::text FROM pg_trigger "
        "WHERE NOT tgisinternal"))}
    return [f"CREATE TRIGGER {trig} BEFORE UPDATE OR DELETE ON {t} "
            "FOR EACH ROW EXECUTE FUNCTION wordsworth_forbid_mutation()"
            for trig, t in _APPEND_ONLY if (trig, t) not in trigs]


def init_schema(engine: Engine, *, attempts: int = 20, lock_timeout: str = "5s",
                wait: float = 30.0) -> None:
    """``KeyServiceBase.metadata.create_all`` plus the append-only trigger on
    ``access_audit`` and ``key_lifecycle_events``. A second run is a no-op:
    ``create_all`` never touches an existing table, and the trigger check
    below skips what is already there. Same lock-timeout-and-retry shape as
    ``wordsworth.db.init_schema`` -- see that function for why."""
    if attempts < 1:
        raise ValueError("init_schema: attempts must be at least 1")
    KeyServiceBase.metadata.create_all(engine)
    for attempt in range(attempts):
        try:
            with engine.begin() as conn:
                conn.execute(text(f"SET LOCAL lock_timeout = '{lock_timeout}'"))
                conn.execute(text(_FORBID_FUNCTION_SQL))
                for stmt in _missing_triggers(conn):
                    conn.execute(text(stmt))
            return
        except OperationalError as exc:
            if not _is_lock_conflict(exc) or attempt == attempts - 1:
                raise
            log.warning("init_schema: lock busy, attempt %d of %d, %.0fs left",
                        attempt + 1, attempts, wait)
            time.sleep(wait)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, class_=Session, future=True, expire_on_commit=False)
