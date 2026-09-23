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


def _is_lock_timeout(exc: OperationalError) -> bool:
    """Postgres meldt een verlopen ``lock_timeout`` als SQLSTATE 55P03.

    Op de tekst matchen zou ook werken tot iemand een andere taal instelt; de
    code is de enige die niet verschuift.
    """
    return getattr(getattr(exc, "orig", None), "sqlstate", None) == "55P03"

# Trigger that makes audit_records append-only at the schema level.
_APPEND_ONLY_SQL = """
CREATE OR REPLACE FUNCTION wordsworth_forbid_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS audit_no_mutation ON audit_records;
CREATE TRIGGER audit_no_mutation
    BEFORE UPDATE OR DELETE ON audit_records
    FOR EACH ROW EXECUTE FUNCTION wordsworth_forbid_mutation();

-- The authorisation trail (key-audit-in-postgres). Same function, same rule.
DROP TRIGGER IF EXISTS key_lifecycle_no_mutation ON key_lifecycle_events;
CREATE TRIGGER key_lifecycle_no_mutation
    BEFORE UPDATE OR DELETE ON key_lifecycle_events
    FOR EACH ROW EXECUTE FUNCTION wordsworth_forbid_mutation();
"""


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


# Additive, idempotent column migrations for databases created before the
# column existed (create_all never alters existing tables). Boring on purpose.
_COLUMN_MIGRATIONS_SQL = """
ALTER TABLE pii_mappings ADD COLUMN IF NOT EXISTS norm_version VARCHAR;
ALTER TABLE grants ADD COLUMN IF NOT EXISTS domain VARCHAR;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS filename VARCHAR;
ALTER TABLE grants ADD COLUMN IF NOT EXISTS role VARCHAR;
"""

# Reveal walks this table on every call; without the index it is a sequential
# scan over every pseudonym in the corpus.
_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_document_pseudonyms_doc
  ON document_pseudonyms (document_id);
-- Every scoped search walks this the other way round: from a dossier to its
-- documents. The primary key covers (dossier, document); this covers the
-- reverse question, "which dossiers is this document in".
CREATE INDEX IF NOT EXISTS idx_dossier_documents_doc
  ON dossier_documents (document_id);
"""


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
                conn.execute(text(_COLUMN_MIGRATIONS_SQL))
                conn.execute(text(_INDEX_SQL))
                conn.execute(text(_APPEND_ONLY_SQL))
            return
        except OperationalError as exc:
            # Alleen het slot is het wachten waard. Een verkeerd wachtwoord of
            # een weggevallen database wordt door wachten niet beter, en twintig
            # pogingen verbergen dan de echte fout.
            if not _is_lock_timeout(exc) or poging == attempts - 1:
                raise
            log.warning("init_schema: slot bezet, poging %d van %d over %.0fs",
                        poging + 1, attempts, wait)
            time.sleep(wait)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, class_=Session, future=True, expire_on_commit=False)
