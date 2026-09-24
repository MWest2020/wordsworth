"""Engine/session factory and schema initialisation.

The append-only guarantee is enforced in the database itself: a BEFORE
UPDATE/DELETE trigger raises. This is the auditable, tamper-resistant form —
not merely the absence of an application code path.
"""
from __future__ import annotations

import logging
import time

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from .config import settings
from .models import Base

log = logging.getLogger(__name__)


#: 55P03 = ``lock_timeout`` expired; 40P01 = chosen as a deadlock victim. Both
#: mean Postgres rolled our transaction back over a lock, so a retry is safe.
#: Matching on the text would work until someone sets another language; the
#: code is the one thing that does not move.
_LOCK_CONFLICTS = {"55P03", "40P01"}


def _is_lock_conflict(exc: OperationalError) -> bool:
    return getattr(getattr(exc, "orig", None), "sqlstate", None) in _LOCK_CONFLICTS

# The function behind the append-only triggers. Replacing a function takes no
# lock on any table, so this one runs every time and a changed body lands.
_FORBID_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION wordsworth_forbid_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;
"""

# A superseded document's pointer is set once (one-document-per-object).
_SUPERSEDED_ONCE_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION wordsworth_superseded_once() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'documents.superseded_by is set once';
END;
$$ LANGUAGE plpgsql;
"""

# Tables that are append-only at the schema level: (trigger, table).
# key_lifecycle_events is the authorisation trail (key-audit-in-postgres).
_APPEND_ONLY = [
    ("audit_no_mutation", "audit_records"),
    ("key_lifecycle_no_mutation", "key_lifecycle_events"),
]


def make_engine(url: str | None = None) -> Engine:
    return create_engine(
        url or settings.database_url,
        future=True,
        # Explicit pool sizing (ADR-0001), not the library default (5+10), tuned
        # to concurrent request volume; pre_ping/recycle guard stale connections.
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
        pool_recycle=1800,
        # Force UTC so timestamptz round-trips are stable for hashing.
        connect_args={"options": "-c timezone=utc"},
    )


# Additive column migrations for databases created before the column existed
# (create_all never alters existing tables): (table, column, type).
_COLUMNS = [
    ("pii_mappings", "norm_version", "VARCHAR"),
    ("grants", "domain", "VARCHAR"),
    ("documents", "filename", "VARCHAR"),
    ("grants", "role", "VARCHAR"),
    ("documents", "superseded_by", "UUID REFERENCES documents(id)"),
]

# (trigger, table) -> its CREATE statement, for the triggers that are not the
# append-only kind.
_OTHER_TRIGGERS = {
    ("superseded_once", "documents"):
        "CREATE TRIGGER superseded_once BEFORE UPDATE OF superseded_by ON documents "
        "FOR EACH ROW WHEN (OLD.superseded_by IS NOT NULL "
        "AND NEW.superseded_by IS DISTINCT FROM OLD.superseded_by) "
        "EXECUTE FUNCTION wordsworth_superseded_once()",
}

# name -> (table, column). Reveal walks document_pseudonyms on every call;
# without its index that is a sequential scan over every pseudonym in the
# corpus. Every scoped search walks dossier_documents the other way round, from
# a dossier to its documents; the primary key covers (dossier, document), this
# covers "which dossiers is this document in".
_INDEXES = {
    "idx_document_pseudonyms_doc": ("document_pseudonyms", "document_id"),
    "idx_dossier_documents_doc": ("dossier_documents", "document_id"),
}


# Unique indexes, by name. Creating one fails while duplicates exist, and it
# should: on a database that still holds copies, run `wordsworth-dedupe` first.
# An init that quietly skipped the constraint would leave the rule unenforced
# without anyone knowing (one-document-per-object, design Decision 6).
_UNIQUE_INDEXES = {
    "uq_documents_live_object_key":
        "CREATE UNIQUE INDEX uq_documents_live_object_key ON documents (object_key) "
        "WHERE superseded_by IS NULL",
}


def _missing_ddl(conn) -> list[str]:
    """The DDL still to do, and nothing else.

    ``ADD COLUMN IF NOT EXISTS`` and ``DROP TRIGGER`` ask for ACCESS EXCLUSIVE
    *before* they find out there is nothing to do. On 2026-09-14, 09-18 and
    09-23 a deploy that changed nothing on ``documents``, ``pii_mappings`` or
    ``audit_records`` still had to wait out every long reader on them, and on
    09-23 lost to one four times running. Asking the catalog first takes no table
    lock; a deploy that adds nothing to a table now never touches it.
    """
    cols = {tuple(r) for r in conn.execute(text(
        "SELECT table_name, column_name FROM information_schema.columns "
        "WHERE table_schema = current_schema()"))}
    trigs = {tuple(r) for r in conn.execute(text(
        "SELECT tgname, tgrelid::regclass::text FROM pg_trigger "
        "WHERE NOT tgisinternal"))}
    ddl = [f"ALTER TABLE {t} ADD COLUMN IF NOT EXISTS {c} {typ}"
           for t, c, typ in _COLUMNS if (t, c) not in cols]
    ddl += [f"CREATE INDEX IF NOT EXISTS {name} ON {t} ({c})"
            for name, (t, c) in _INDEXES.items()
            if conn.execute(text("SELECT to_regclass(:n)"), {"n": name}).scalar() is None]
    ddl += [f"CREATE TRIGGER {trig} BEFORE UPDATE OR DELETE ON {t} "
            "FOR EACH ROW EXECUTE FUNCTION wordsworth_forbid_mutation()"
            for trig, t in _APPEND_ONLY if (trig, t) not in trigs]
    ddl += [sql for key, sql in _OTHER_TRIGGERS.items() if key not in trigs]
    ddl += [sql for name, sql in _UNIQUE_INDEXES.items()
            if conn.execute(text("SELECT to_regclass(:n)"), {"n": name}).scalar() is None]
    return ddl


def init_schema(engine: Engine, *, attempts: int = 20, lock_timeout: str = "5s",
                wait: float = 30.0) -> None:
    """Apply the schema migration: tables + columns + the append-only trigger.

    Each attempt is bounded by a lock timeout, because the statements below
    need ACCESS EXCLUSIVE on a table the API is reading. Without a bound a
    blocked migration does not merely wait: a queued ACCESS EXCLUSIVE request
    parks every later reader behind it, so one stalled init takes the whole API
    down with it. On 2026-09-14 an init during a running reprocess was broken
    up by Postgres' own deadlock detector — that is luck, not a design.

    Failing fast per attempt, patient across attempts. The earlier version said
    "a retry that starts a second later usually finds the lock free" and left
    the retrying to the Job's own backoff. On 2026-09-18 that turned out to be
    wrong by an order of magnitude: a herstel-Job held a read transaction open
    for ten minutes at a stretch, the Job's six attempts were spent inside the
    first of those, and the rollout failed. So the waiting happens here now,
    where the budget is visible: ``attempts`` tries with ``wait`` seconds
    between them — twenty times thirty seconds, long enough to outlast an
    ordinary long read, and never holding a lock request open while it waits.

    A caller that would rather hear about it immediately passes ``attempts=1``.
    """
    if attempts < 1:
        # Anders zou de lus nul keer draaien en zou deze functie stil
        # terugkeren zonder de migratie te hebben gedaan -- het soort succes
        # waar niemand achter komt.
        raise ValueError("init_schema: attempts moet minstens 1 zijn")
    Base.metadata.create_all(engine)
    for poging in range(attempts):
        try:
            with engine.begin() as conn:
                # SET LOCAL: scoped to this transaction, gone on commit.
                conn.execute(text(f"SET LOCAL lock_timeout = '{lock_timeout}'"))
                conn.execute(text(_FORBID_FUNCTION_SQL))
                conn.execute(text(_SUPERSEDED_ONCE_FUNCTION_SQL))
                for stmt in _missing_ddl(conn):
                    conn.execute(text(stmt))
            return
        except OperationalError as exc:
            # Alleen het slot is het wachten waard. Een verkeerd wachtwoord of
            # een weggevallen database wordt door wachten niet beter, en twintig
            # pogingen verbergen dan de echte fout.
            if not _is_lock_conflict(exc) or poging == attempts - 1:
                raise
            log.warning("init_schema: slot bezet, poging %d van %d over %.0fs",
                        poging + 1, attempts, wait)
            time.sleep(wait)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, class_=Session, future=True, expire_on_commit=False)
