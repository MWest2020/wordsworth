"""``POST /v1/reveal/decide`` and ``POST /v1/reveal`` (design.md "Requests",
"Order inside the service"). ``decide`` judges whether a caller is covered
and for which types; decrypts nothing and writes nothing. ``reveal`` judges
again, from scratch, and reveals the requested tokens that are registered
for the document and of an authorised type; audits; returns values (text
view) or only the resolved tokens (PDF view). Token resolution and the
audit payload live in ``reveal_resolve.py`` (this file hit the 200-line
limit)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import audit, identity, reveal_gate, reveal_resolve
from .config import settings
from .db import make_engine, make_session_factory

router = APIRouter()


class RevealDecideRequest(BaseModel):
    document_id: UUID
    grant_id: str
    types: list[str] | None = None
    assertion: str
    vc: str | None = None


class RevealDecideResponse(BaseModel):
    document_id: UUID
    authorized_types: list[str]
    withheld_types: list[str]


class RevealRequest(RevealDecideRequest):
    tokens: list[str] = []
    view: Literal["text", "pdf"]


def _session_factory(request: Request):
    app = request.app
    if app.state.session_factory is None:
        if app.state.engine is None:
            app.state.engine = make_engine()
        app.state.session_factory = make_session_factory(app.state.engine)
    return app.state.session_factory


def _identity_for(request: Request):
    """One ``Identity`` per process (``api_originals.py``'s ``doc_keys``
    pattern): its JWKS cache stays warm across requests."""
    app = request.app
    if app.state.identity is None:
        app.state.identity = identity.build_identity(
            settings.oidc_issuer, settings.oidc_audience, settings.oidc_jwks_url)
    return app.state.identity


def _vc_public_key():
    if not settings.vc_public_key_pem:
        return None
    from wordsworth.vc import load_public_key_pem
    return load_public_key_pem(settings.vc_public_key_pem)


def _authenticate(body: RevealDecideRequest, request: Request) -> str:
    """Steps 2-3 of design.md's order: configured, else 503; the assertion
    verified, else 401 -- the same body for every reason, no database read."""
    if not settings.oidc_issuer or not settings.oidc_audience:
        raise HTTPException(503, detail="reveal not configured")
    try:
        return identity.verify_assertion(body.assertion, _identity_for(request))
    except identity.AssertionNotAccepted:
        raise HTTPException(401, detail="assertion not accepted")


def _decide(session: Session, body: RevealDecideRequest, caller: str) -> reveal_gate.Decision:
    return reveal_gate.decide(
        session, body.grant_id, body.document_id, body.types,
        caller=caller, allow_global=settings.allow_global_grants,
        now=datetime.now(timezone.utc), vc_public_key=_vc_public_key(),
        vc_expected_vct=settings.vc_expected_vct or None,
        vc_expected_issuer=settings.vc_expected_issuer or None,
        vc_required=settings.vc_required, x_vc=body.vc)


@router.post("/v1/reveal/decide", response_model=RevealDecideResponse)
def reveal_decide(body: RevealDecideRequest, request: Request) -> RevealDecideResponse:
    caller = _authenticate(body, request)
    with _session_factory(request)() as session:
        decision = _decide(session, body, caller)
    return RevealDecideResponse(
        document_id=body.document_id,
        authorized_types=sorted(decision.authorized),
        withheld_types=sorted(decision.withheld))


@router.post("/v1/reveal")
def reveal(body: RevealRequest, request: Request) -> dict:
    max_tokens = settings.reveal_max_tokens
    if len(body.tokens) > max_tokens:
        raise HTTPException(413, detail=f"too many tokens (limit {max_tokens})")

    caller = _authenticate(body, request)
    service_caller = request.state.service_caller

    with _session_factory(request)() as session:
        decision = _decide(session, body, caller)
        resolved, resolved_types = reveal_resolve.resolve_tokens(
            session, request, body.document_id, body.tokens, decision.authorized)
        record = audit.append_access(
            session, event="reveal", service_caller=service_caller, caller=caller,
            document_id=body.document_id,
            payload=reveal_resolve.audit_payload(body, decision, resolved, resolved_types))
        session.commit()

    audit_block = {"seq": record.seq, "hash": record.hash,
                   "actor": decision.grant.recipient, "grant_id": body.grant_id,
                   "caller": caller}
    if decision.grant.role:
        audit_block["role"] = decision.grant.role
        if decision.grant.document_id is None:
            audit_block["global_by_role"] = True

    response = {
        "document_id": str(body.document_id),
        "authorized_types": sorted(decision.authorized),
        "withheld_types": sorted(decision.withheld),
        "resolved_tokens": sorted(resolved),
        "resolved_types": sorted(record.payload["types"]),
        "audit": audit_block,
    }
    if body.view == "text":
        response["values"] = resolved
    return response
