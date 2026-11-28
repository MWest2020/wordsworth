"""``POST /v1/pseudonymise`` (design.md "POST /v1/pseudonymise"). Values to
tokens, the encrypted value stored, the token registered for the document.
No route here returns a clear value; only reveal does
(``key-service-reveal``)."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, model_validator
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from wordsworth.keys import DurableKeyProvider
from wordsworth.pseudonymizer import Pseudonymizer

from . import audit, known
from .config import settings
from .db import make_engine, make_session_factory
from .models import DocumentToken
from .stores_pii import PostgresKeyVaultStore, PostgresMappingStore

#: The token alphabet of ``pseudonymizer._PSEUDONYM_RE`` once upper-cased:
#: every token this service mints stays recognisable and revealable. No
#: closed list -- an unknown detector type is accepted, not refused
#: (design.md "Type labels").
_LABEL_RE = re.compile(r"^[A-Za-z0-9_]+$")

router = APIRouter()


class PseudonymiseItem(BaseModel):
    type: str
    value: str

    @model_validator(mode="after")
    def _valid_type(self):
        if not _LABEL_RE.fullmatch(self.type):
            raise ValueError("type must match [A-Za-z0-9_]+")
        return self


class PseudonymiseRequest(BaseModel):
    document_id: UUID
    domain: str
    items: list[PseudonymiseItem] = []

    @model_validator(mode="after")
    def _valid_domain(self):
        if not self.domain or "/" in self.domain:
            raise ValueError("domain must be non-empty and contain no '/'")
        return self


class PseudonymiseResponse(BaseModel):
    document_id: UUID
    tokens: list[str]


def _session_factory(request: Request):
    app = request.app
    if app.state.session_factory is None:
        if app.state.engine is None:
            app.state.engine = make_engine()
        app.state.session_factory = make_session_factory(app.state.engine)
    return app.state.session_factory


def _transit_for(request: Request):
    app = request.app
    if app.state.transit_for is None:
        from wordsworth.transit import transit_factory
        app.state.transit_for = transit_factory(
            settings.openbao_url, settings.openbao_token)
    return app.state.transit_for


def _register_tokens(session: Session, document_id: UUID, tokens: list[str]) -> int:
    """Register each token for ``document_id`` with ``source = "minted"``.
    Idempotent, additive only (``ON CONFLICT DO NOTHING``) -- re-pseudonymising
    a document adds tokens and never removes one (design.md "The token
    registry"). Counts the actual inserts via ``RETURNING``: the DBAPI's
    ``rowcount`` for an ``ON CONFLICT DO NOTHING`` insert is driver-defined
    and not reliable (psycopg reports -1, "unknown")."""
    if not tokens:
        return 0
    now = datetime.now(timezone.utc)
    rows = [{"document_id": document_id, "token": token, "source": "minted",
            "created_at": now} for token in sorted(set(tokens))]
    stmt = pg_insert(DocumentToken).values(rows).on_conflict_do_nothing(
        index_elements=["document_id", "token"]).returning(DocumentToken.token)
    return len(session.execute(stmt).fetchall())


@router.post("/v1/pseudonymise", response_model=PseudonymiseResponse)
def pseudonymise(body: PseudonymiseRequest, request: Request) -> PseudonymiseResponse:
    max_items = settings.pseudonymise_max_items
    if len(body.items) > max_items:
        raise HTTPException(
            422, detail=f"items exceeds the configured maximum of {max_items}")

    service_caller = request.state.service_caller
    session_factory = _session_factory(request)

    with session_factory() as session:
        known.lock_registry(session)
        try:
            known.ensure_known(session, body.document_id, body.domain)
        except known.DomainConflict:
            raise HTTPException(
                409, detail="document is registered in another domain")
        except known.DocumentDeleted:
            raise HTTPException(410, detail="document deleted")

        key_provider = DurableKeyProvider(
            PostgresKeyVaultStore(session),
            _transit_for(request)(settings.transit_kek),
            cache_ttl_seconds=settings.key_cache_ttl)
        pseudonymizer = Pseudonymizer(
            key_provider, PostgresMappingStore(session), domain=body.domain)

        tokens: list[str] = []
        counts: dict[str, int] = {}
        try:
            for item in body.items:
                tokens.append(pseudonymizer.pseudonym(item.type, item.value))
                label = item.type.upper()
                counts[label] = counts.get(label, 0) + 1
        except Exception as exc:
            raise HTTPException(503, detail="key service unavailable") from exc

        new_rows = _register_tokens(session, body.document_id, tokens)

        audit.append_access(
            session, event="pseudonymise", service_caller=service_caller,
            document_id=body.document_id,
            payload={"counts": counts, "new_registry_rows": new_rows})

        session.commit()

    return PseudonymiseResponse(document_id=body.document_id, tokens=tokens)
