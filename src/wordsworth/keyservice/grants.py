"""The service's own grant reader: ``wordsworth.grants.Grant`` and its pure
``authorize``/``permitted_types`` are reused unchanged (design.md "Who
decides what") -- only the row they read is the service's own
(``models_access.GrantRecord``), never wordsworth's. No issue/revoke here:
grants are seeded as rows in this change; the management endpoints come
with ``key-service-cutover``."""
from __future__ import annotations

from sqlalchemy.orm import Session

from wordsworth.grants import Grant
from wordsworth.keys import DEFAULT_DOMAIN

from .models_access import GrantRecord


class KeyServiceGrantStore:
    def __init__(self, session: Session):
        self._session = session

    def get(self, grant_id: str) -> Grant | None:
        row = self._session.get(GrantRecord, grant_id)
        if row is None:
            return None
        return Grant(
            grant_id=row.grant_id,
            recipient=row.recipient,
            allowed_types=list(row.allowed_types),
            document_id=row.document_id,
            status=row.status,
            created_at=row.created_at,
            revoked_at=row.revoked_at,
            expires_at=row.expires_at,
            actor=row.actor,
            domain=row.domain or DEFAULT_DOMAIN,  # legacy NULL = default domain
            role=row.role,
        )
