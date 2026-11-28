"""Who is calling, for a reveal (design.md "Identity"): the raw Keycloak JWT
wordsworth received, forwarded in the request body as ``assertion``. Wraps
``access_identity.Verifier.oidc`` and ``email_from`` under this service's own
``KEYSERVICE_OIDC_*`` configuration, adding the ``nbf`` check that module
does not perform -- wordsworth's ``Verifier`` is never changed.

Every refusal -- missing, forged, expired, not-yet-valid, wrong issuer,
foreign audience, or a missing/unverified email -- is one
``AssertionNotAccepted``, so a route maps every cause to the same 401 body
(design.md "Order inside the service"). A Cloudflare Access assertion is
refused the same way: this service's ``Verifier`` only ever names one OIDC
issuer, and an Access token fails that issuer/audience check like any
other wrong-issuer token -- no separate check is needed."""
from __future__ import annotations

import base64
import json
import time

from wordsworth import access_identity


class AssertionNotAccepted(Exception):
    """Any reason this assertion is not accepted. The message is for logs
    and tests only -- a route never echoes it; every cause gets the same
    body, ``{"detail": "assertion not accepted"}``."""


def build_identity(issuer: str, audience: str, jwks_url: str = "") -> access_identity.Identity:
    """One ``Identity`` per process (the caller keeps it on ``app.state``,
    the same shape as ``doc_keys``/``transit_for``): its JWKS cache stays
    warm across requests."""
    verifier = access_identity.Verifier.oidc(issuer, audience, jwks_url=jwks_url)
    return access_identity.Identity(verifier)


def _nbf_ok(token: str, now: float) -> bool:
    """The token already verified by ``email_from`` in this same call --
    decoding its payload again to read ``nbf`` is safe, never a second
    signature check."""
    try:
        _, body_b64, _ = token.split(".")
        body = json.loads(base64.urlsafe_b64decode(body_b64 + "=" * (-len(body_b64) % 4)))
    except Exception:
        return False
    nbf = body.get("nbf")
    if nbf is None:
        return True
    try:
        return float(nbf) <= now
    except (TypeError, ValueError):
        return False


def verify_assertion(token: str, identity: access_identity.Identity, *,
                      now: float | None = None) -> str:
    """The verified email on ``token``, or raise ``AssertionNotAccepted``.
    Signature, algorithm, issuer, audience, expiry and the verified-email
    requirement are ``access_identity.email_from``, unchanged; ``nbf`` is
    checked here, after that call has already verified the signature."""
    now = time.time() if now is None else now
    if not token:
        raise AssertionNotAccepted("missing assertion")
    try:
        email = access_identity.email_from(token, identity.keys(now), identity.verifier, now)
    except access_identity.AccessError as exc:
        raise AssertionNotAccepted(str(exc)) from exc
    if not _nbf_ok(token, now):
        raise AssertionNotAccepted("assertion not yet valid")
    return email
