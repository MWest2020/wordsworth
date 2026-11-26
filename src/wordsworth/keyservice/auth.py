"""Service-to-service authentication: one Bearer token per calling service,
fail-closed. A pure ASGI middleware (not a FastAPI dependency), because a
dependency runs after the body is parsed; this answers before that and
before any database read (design.md "Service authentication") -- it never
calls ``receive`` and never opens a session.

The service token names the CALLING SERVICE, never a person -- a person's
identity is a ``key-service-reveal`` concern, verified by the service itself.
The two are never collapsed into one caller, so this module never mounts
wordsworth's ``ApiKeyAuthMiddleware``."""
from __future__ import annotations

import hmac

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

_UNAUTHORIZED = {"detail": "invalid or missing service token"}


def _label_for(token: str, tokens: dict[str, str]) -> str | None:
    """The label for ``token``, or ``None``. Compares against every
    configured token (never a dict lookup) so a near-miss takes the same
    time whichever configured token it is close to, and an empty token
    never matches a configured empty label."""
    if not token:
        return None
    label = None
    for candidate, candidate_label in tokens.items():
        if hmac.compare_digest(token, candidate):
            label = candidate_label
    return label


class ServiceTokenMiddleware:
    """Requires ``Authorization: Bearer <token>`` on every path under
    ``prefix``. An empty token set refuses every call under the prefix --
    unlike wordsworth's ``ApiKeyAuthMiddleware``, which opens when no key is
    configured: an open key service is the one thing this split exists to
    prevent."""

    def __init__(self, app: ASGIApp, tokens: dict[str, str], *,
                 prefix: str = "/v1/") -> None:
        self.app = app
        self.tokens = dict(tokens)
        self.prefix = prefix

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if scope["type"] != "http" or not path.startswith(self.prefix):
            await self.app(scope, receive, send)
            return
        header = next((v for k, v in scope.get("headers", ())
                       if k == b"authorization"), b"").decode("latin-1")
        token = header[7:] if header.lower().startswith("bearer ") else ""
        label = _label_for(token, self.tokens)
        if label is None:
            await JSONResponse(_UNAUTHORIZED, status_code=401)(scope, receive, send)
            return
        scope.setdefault("state", {})["service_caller"] = label
        await self.app(scope, receive, send)
