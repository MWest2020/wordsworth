"""Engine/session factory and schema initialisation.

The append-only guarantee is enforced in the database itself: a BEFORE
UPDATE/DELETE trigger raises. This is the auditable, tamper-resistant form —
not merely the absence of an application code path.
"""
from __future__ import annotations

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .config import settings
from .models import Base

# Trigger that makes audit_records append-only at the schema level.
_APPEND_ONLY_SQL = """
CREATE OR REPLACE FUNCTION wordsworth_forbid_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_records is append-only';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS audit_no_mutation ON audit_records;
CREATE TRIGGER audit_no_mutation
    BEFORE UPDATE OR DELETE ON audit_records
    FOR EACH ROW EXECUTE FUNCTION wordsworth_forbid_mutation();
"""


def make_engine(url: str | None = None) -> Engine:
    return create_engine(
        url or settings.database_url,
        future=True,
        # Force UTC so timestamptz round-trips are stable for hashing.
        connect_args={"options": "-c timezone=utc"},
    )


def init_schema(engine: Engine) -> None:
    """Apply the schema migration: tables + the append-only trigger."""
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text(_APPEND_ONLY_SQL))


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, class_=Session, future=True, expire_on_commit=False)
