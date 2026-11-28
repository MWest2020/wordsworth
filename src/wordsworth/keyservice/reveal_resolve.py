"""Steps 9-10 of design.md "Order inside the service": resolve the distinct
requested tokens that are registered for this document and of an
authorised type, and build the audit payload for the record step 10
appends. Split out of ``api_reveal.py`` only because that file hit the
200-line limit (design.md "Layout": "split further if the rule needs it")."""
from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from wordsworth.crypto import decrypt
from wordsworth.keys import DurableKeyProvider
from wordsworth.pii_categories import category_of
from wordsworth.pseudonymizer import label_of

from . import reveal_gate
from .config import settings
from .models import DocumentToken
from .stores_pii import PostgresKeyVaultStore, PostgresMappingStore


def _transit_for(request: Request):
    app = request.app
    if app.state.transit_for is None:
        from wordsworth.transit import transit_factory
        app.state.transit_for = transit_factory(
            settings.openbao_url, settings.openbao_token)
    return app.state.transit_for


def resolve_tokens(session: Session, request: Request, document_id: UUID,
                   tokens: list[str], authorized: set[str]) -> tuple[dict[str, str], set[str]]:
    """Each distinct requested token, in sorted order, revealed only when
    registered for this document, of an authorised type, with a mapping and
    a resolving key -- a missing key version leaves it unresolved, never a
    503. Any other key-backend failure is 503, raised before any record is
    written."""
    registered: set[str] = set()
    if tokens:
        registered = set(session.execute(
            select(DocumentToken.token)
            .where(DocumentToken.document_id == document_id,
                   DocumentToken.token.in_(set(tokens)))
        ).scalars().all())

    key_provider = DurableKeyProvider(
        PostgresKeyVaultStore(session), _transit_for(request)(settings.transit_kek),
        cache_ttl_seconds=settings.key_cache_ttl)
    mapping_store = PostgresMappingStore(session)

    resolved: dict[str, str] = {}
    resolved_types: set[str] = set()
    try:
        for token in sorted(set(tokens)):
            if token not in registered:
                continue
            label = label_of(token)
            if label not in authorized:
                continue
            mapping = mapping_store.get(token)
            if mapping is None:
                continue
            try:
                key = key_provider.key(mapping.key_id)
            except KeyError:
                continue
            resolved[token] = decrypt(key.material, mapping.ciphertext, mapping.nonce)
            resolved_types.add(label)
    except Exception as exc:
        raise HTTPException(503, detail="key service unavailable") from exc
    return resolved, resolved_types


def audit_payload(body, decision: "reveal_gate.Decision",
                  resolved: dict[str, str], resolved_types: set[str]) -> dict:
    """design.md step 10's record fields, minus the columns
    (``document_id``, ``service_caller``, ``caller``) ``audit.append_access``
    already carries outside the payload."""
    payload = {
        "actor": decision.grant.recipient,
        "grant_id": body.grant_id,
        "view": body.view,
        "requested_types": sorted({t.upper() for t in body.types}) if body.types else [],
        "requested_all": not body.types,
        "authorized_types": sorted(decision.authorized),
        "pseudonyms": sorted(resolved),
        "types": sorted(resolved_types),
        "categories": sorted({category_of(t) for t in resolved_types}),
    }
    if decision.grant.role:
        payload["role"] = decision.grant.role
        if decision.grant.document_id is None:
            payload["global_by_role"] = True
    payload.update(decision.vc_audit)
    return payload
