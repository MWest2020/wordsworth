# SPDX-License-Identifier: MIT
"""Wat de browser van dit scherm mag maken (securityreview 18-09).

Twee gaten met één oorzaak: de console gaat ervan uit dat de browser doet wat wij
bedoelen. Dat doet hij niet — hij doet wat de pagina hem vraagt, en dat kan een
ándere pagina zijn.

**Clickjacking.** Zonder `frame-ancestors` kan iemand `/console/documents/<id>`
in een onzichtbare iframe zetten en de Onthul-knop onder een cursor schuiven. Het
resultaat leest hij niet — CORS staat dicht — maar de onthulling gebeurt wél, en
het auditspoor noemt het slachtoffer. Een append-only spoor met een onware naam
erin is niet te repareren.

**Login-CSRF.** `POST /console/login` is auth-vrij en zet een cookie. Een pagina
elders kan die post doen en zo het callerlabel van een bezoeker wisselen naar een
sleutel die de aanvaller kent. Geen rechtenverhoging — het is andermans sleutel —
maar wel valse attributie, en `Path=/` maakt dat voor de hele API geldig.

Waarom Origin en geen token: een token vergt sessiestatus die er niet is, en een
formulier dat je zonder sessie moet kunnen openen. De Origin-controle is
stateless en dicht voor precies dit geval. Wat hij NIET dicht doet staat hieronder
bij `same_origin`.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

#: Alles van onszelf. `style-src` staat inline toe omdat de stylesheet in de
#: sjablonen staat; scripts niet, en die staan er ook niet inline.
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
       "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
       "form-action 'self'; frame-ancestors 'none'; base-uri 'none'")

HEADERS = {
    "content-security-policy": CSP,
    # Dubbelop met frame-ancestors, voor browsers die dat nog niet kennen.
    "x-frame-options": "DENY",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
}


_DEFAULT_PORT = {"http": 80, "https": 443}


def same_origin(origin: str, host: str) -> bool:
    """Komt dit verzoek van onze eigen pagina?

    Een ontbrekende Origin telt als eigen: curl, een CLI en de tests sturen hem
    niet, en die willen we niet buitensluiten. Dat is ook precies de grens van
    deze verdediging — ze houdt een browser tegen, geen script. Voor dit geval is
    dat genoeg: het gat is dat een BROWSER van een andere pagina een cookie kan
    laten zetten.

    Otherwise hostname and port must match the Host header exactly. Until
    2026-09-24 this was `origin.endswith(host-without-port)`: an Origin with a
    port (`http://localhost:8000`) never matched, and with no boundary before
    the suffix any hostname ending in ours did. A Host without a port is taken
    to be on the default port of the scheme the browser used, because that is
    how a browser writes an Origin.
    """
    if not origin:
        return True
    o = urlsplit(origin.strip())
    if o.scheme not in _DEFAULT_PORT or not o.hostname:
        return False            # "null", a file: page, anything opaque
    try:
        h = urlsplit("//" + host.strip())
        o_port = o.port or _DEFAULT_PORT[o.scheme]
        h_port = h.port or _DEFAULT_PORT[o.scheme]
    except ValueError:          # a port that is not a number
        return False
    return o.hostname == h.hostname and o_port == h_port


class ConsoleSafety:
    """Zet de headers, en weigert een cross-site post op de console."""

    def __init__(self, app: ASGIApp, prefix: str = "/console") -> None:
        self.app = app
        self.prefix = prefix

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope.get("path", "").startswith(self.prefix):
            await self.app(scope, receive, send)
            return
        headers = {k.decode(): v.decode() for k, v in scope.get("headers", [])}
        if scope.get("method") == "POST" and not same_origin(
                headers.get("origin", ""), headers.get("host", "")):
            await JSONResponse({"detail": "cross-site request refused"},
                               status_code=403)(scope, receive, send)
            return

        async def met_headers(bericht):
            if bericht["type"] == "http.response.start":
                bestaand = list(bericht.get("headers", []))
                aanwezig = {k.decode().lower() for k, _ in bestaand}
                bestaand += [(k.encode(), v.encode()) for k, v in HEADERS.items()
                             if k not in aanwezig]
                bericht = {**bericht, "headers": bestaand}
            await send(bericht)

        await self.app(scope, receive, met_headers)
