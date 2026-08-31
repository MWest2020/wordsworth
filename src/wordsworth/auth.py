"""Optional per-caller API-key authentication (opt-in, default off).

When ``WORDSWORTH_API_KEYS`` is set, mutating/PII endpoints require a valid
``X-API-Key`` header mapping to a caller label; that label is recorded as the
audit caller on reveal. When unset, the middleware is never mounted and the
tailnet-internal API stays open — behaviour is identical to before (non-
breaking). Keys are never logged. A stronger scheme (OIDC / mTLS) is the heavier
future option; this is the minimal key→label layer."""
from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


def parse_api_keys(raw: str) -> dict[str, str]:
    """Parse ``label:key`` comma-separated pairs into {key: label}. Malformed
    entries (no colon, empty label/key) are skipped safely; empty input → {}."""
    keys: dict[str, str] = {}
    for entry in (raw or "").split(","):
        entry = entry.strip()
        if not entry or ":" not in entry:
            continue
        label, _, key = entry.partition(":")
        label, key = label.strip(), key.strip()
        if label and key:
            keys[key] = label
    return keys


def authorize_corpus_read(caller: str | None, allowed_labels: list[str]) -> bool:
    """Whether ``caller`` may read full de-identified document text
    (``/documents/{id}/anonymized`` and ``/export/anonymized.zip``).

    An empty ``allowed_labels`` means the corpus-read scope is OFF — any caller
    is permitted (unchanged, non-breaking). When non-empty the scope is ON and
    only callers whose label is listed may read full text; everyone else is
    denied. Fail-closed: a ``None`` caller (auth off) is denied once the scope
    is set, so enabling the scope requires api-key auth to be on."""
    if not allowed_labels:
        return True
    return caller in set(allowed_labels)


class ApiKeyAuthMiddleware:
    """ASGI middleware: require a valid ``X-API-Key`` on every path except the
    exempt ops probes. Mounted only when there is at least one configured key,
    so an empty key set leaves the API open. On success the caller's label is
    stashed at ``scope['state']['caller']`` for downstream audit attribution."""

    def __init__(self, app: ASGIApp, keys: dict[str, str], exempt: frozenset[str]) -> None:
        self.app = app
        self.keys = dict(keys)
        self.exempt = exempt

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path", "") in self.exempt:
            await self.app(scope, receive, send)
            return
        key = Request(scope, receive).headers.get("x-api-key", "")
        label = self.keys.get(key)
        if label is None:
            # 401 with no hint about which/why — and never echo the key.
            await JSONResponse({"detail": "invalid or missing API key"},
                               status_code=401)(scope, receive, send)
            return
        scope.setdefault("state", {})["caller"] = label
        await self.app(scope, receive, send)
