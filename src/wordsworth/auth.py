"""Optional per-caller API-key authentication (opt-in, default off).

When ``WORDSWORTH_API_KEYS`` is set, mutating/PII endpoints require a valid
``X-API-Key`` header mapping to a caller label; that label is recorded as the
audit caller on reveal. When unset, the middleware is never mounted and the
tailnet-internal API stays open — behaviour is identical to before (non-
breaking). Keys are never logged. A stronger scheme (OIDC / mTLS) is the heavier
future option; this is the minimal key→label layer."""
from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
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


def authorize_grant_issue(caller: str | None, issuer_labels: list[str],
                          auth_enabled: bool) -> bool:
    """Mag deze caller een reveal-grant uitgeven of intrekken?

    Zonder api-key-auth (``auth_enabled`` False) is er geen caller om op te
    beslissen en verandert er niets — dat is de bestaande, gedocumenteerde
    tailnet-interne modus. Met auth aan geldt least privilege: alleen labels uit
    ``issuer_labels``. Een lege lijst weigert dan iedereen, want een grant minten
    is het zwaarste recht in dit systeem en hoort een expliciete keuze te zijn.
    """
    if not auth_enabled:
        return True
    return bool(caller) and caller in set(issuer_labels)


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


def wants_html(accept: str) -> bool:
    """Is this a browser navigation rather than an API call?

    ``text/html`` in Accept is what a navigating browser sends and what a
    programmatic client (which sends ``*/*`` or asks for JSON) does not. Crude,
    and the crudeness is the point: the alternative is guessing from User-Agent,
    which is a much worse guess.
    """
    return "text/html" in (accept or "").lower()


#: Cookie the console logs in with. A browser cannot set ``X-API-Key`` on a
#: plain navigation, so the console needs a second TRANSPORT for the key — not a
#: second check. Same key set, same label, same middleware; only the envelope
#: differs. Putting the key in a query string instead would leak it into logs,
#: history and referrers.
CONSOLE_COOKIE = "ww_console"


class ApiKeyAuthMiddleware:
    """ASGI middleware: require a valid ``X-API-Key`` on every path except the
    exempt ops probes. Mounted only when there is at least one configured key,
    so an empty key set leaves the API open. On success the caller's label is
    stashed at ``scope['state']['caller']`` for downstream audit attribution.

    The key may also arrive in the ``ww_console`` cookie (see CONSOLE_COOKIE).
    One decision point, two transports."""

    def __init__(self, app: ASGIApp, keys: dict[str, str], exempt: frozenset[str],
                 login_path: str | None = None,
                 exempt_prefixes: tuple[str, ...] = ()) -> None:
        self.app = app
        self.keys = dict(keys)
        self.exempt = exempt
        # Whole subtrees that carry nothing worth gating — the console's fonts.
        # They also have to be reachable from the login page, which is itself
        # exempt: a login screen rendered without its letters is a broken door.
        self.exempt_prefixes = exempt_prefixes
        # Where to send a person. None when there is no console mounted: sending
        # a browser to a route that answers 404 replaces the wall with a circle.
        self.login_path = login_path

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if (scope["type"] != "http" or path in self.exempt
                or path.startswith(self.exempt_prefixes or ())):
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive)
        key = request.headers.get("x-api-key", "") or request.cookies.get(
            CONSOLE_COOKIE, "")
        label = self.keys.get(key)
        if label is None:
            # A person gets a page; a program gets the API error. A 303 to an
            # HTML form is the wrong answer for a client that will try to parse
            # it, and a JSON body is the wrong answer for someone who just typed
            # the hostname into a browser.
            if self.login_path and wants_html(request.headers.get("accept", "")):
                await RedirectResponse(self.login_path, status_code=303)(
                    scope, receive, send)
                return
            # 401 with no hint about which/why — and never echo the key.
            await JSONResponse({"detail": "invalid or missing API key"},
                               status_code=401)(scope, receive, send)
            return
        scope.setdefault("state", {})["caller"] = label
        await self.app(scope, receive, send)
