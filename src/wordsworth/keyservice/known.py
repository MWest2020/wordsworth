"""``known_documents``: the service's first-sight record of every document
it has seen, and the registry advisory lock that guards it and
``document_tokens`` (design.md "known_documents", "Locks"). The one
function here is reused by ``seal`` (``key-service-originals``); the lock
is reused by ``seal`` and ``DELETE /v1/documents`` (``key-service-delete``)
too."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from .models import KnownDocument

#: design.md "Locks", row 1 -- taken by ``pseudonymise``, ``seal`` and
#: ``DELETE /v1/documents``, before the ``known_documents`` row.
REGISTRY_LOCK_KEY = 4781


class DomainConflict(Exception):
    """A document already known under a different domain (409)."""


class DocumentDeleted(Exception):
    """A document is tombstoned: ``deleted_at`` is set (410)."""


def lock_registry(session: Session) -> None:
    """Take the registry advisory lock now, until the transaction ends.
    Flushes first, same reason as wordsworth's ``audit.lock_chain``: a
    pending row change must reach the database before the lock, not under
    it."""
    session.flush()
    session.execute(text("SELECT pg_advisory_xact_lock(:k)"),
                    {"k": REGISTRY_LOCK_KEY})


def ensure_known(session: Session, document_id: UUID, domain: str) -> None:
    """Record ``document_id``'s domain on first sight. Raises
    ``DomainConflict`` for a later call with a different domain, and
    ``DocumentDeleted`` for a tombstoned document. The caller holds the
    registry lock (``lock_registry``) first."""
    row = session.get(KnownDocument, document_id)
    if row is None:
        session.add(KnownDocument(id=document_id, domain=domain,
                                  registered_at=datetime.now(timezone.utc)))
        session.flush()
        return
    if row.deleted_at is not None:
        raise DocumentDeleted(str(document_id))
    if row.domain != domain:
        raise DomainConflict(str(document_id))
