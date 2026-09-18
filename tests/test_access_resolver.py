# SPDX-License-Identifier: MIT
"""Resolving a request to a person, and the preflight (access-identity).

Split from `test_access_identity` at the seam where the tests stop being about
one signature and start being about a request.
"""
import base64
import json

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from wordsworth.access_identity import (Verifier, email_from,
                                        public_keys)

TEAM = "raspy-wood-e123.cloudflareaccess.com"
AUD = "320841be57b2e469adbef09614573240756da5f3a188df87b6fb761d40e65d65"
VERIFIER = Verifier(team_domain=TEAM, audience=AUD)
NU = 1_789_700_000.0


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _jwks(key, kid="k1"):
    n = key.public_key().public_numbers()
    return {"keys": [{"kty": "RSA", "kid": kid, "alg": "RS256",
                      "n": _b64(n.n.to_bytes((n.n.bit_length() + 7) // 8, "big")),
                      "e": _b64(n.e.to_bytes((n.e.bit_length() + 7) // 8, "big"))}]}


def _token(key, kid="k1", alg="RS256", **claims):
    body = {"aud": [AUD], "iss": f"https://{TEAM}", "exp": NU + 3600,
            "email": "mark@westerweel.work"}
    body.update(claims)
    head = _b64(json.dumps({"alg": alg, "kid": kid}).encode())
    payload = _b64(json.dumps(body).encode())
    sig = key.sign(f"{head}.{payload}".encode(), padding.PKCS1v15(), hashes.SHA256())
    return f"{head}.{payload}.{_b64(sig)}"


@pytest.fixture
def key():
    return _key()


@pytest.fixture
def keys(key):
    return public_keys(VERIFIER, fetch=lambda url: _jwks(key))


# --- the middleware: a person instead of a keyring -------------------------

class _Req:
    def __init__(self, headers):
        self.headers = headers


def _identity(key, **kw):
    from wordsworth.access_identity import Identity

    return Identity(VERIFIER, fetch=lambda url: _jwks(key), **kw)


def test_the_readable_header_is_never_a_source(key):
    """It arrives on every path, including the ones that do not pass the
    provider. Trusting it would make the tailnet route a way to claim anyone."""
    ident = _identity(key)
    req = _Req({"cf-access-authenticated-user-email": "mark@westerweel.work"})
    assert ident.caller(req, NU) is None


def test_a_verified_assertion_names_the_person(key):
    ident = _identity(key)
    req = _Req({"cf-access-jwt-assertion": _token(key)})
    assert ident.caller(req, NU) == "mark@westerweel.work"


def test_a_forged_assertion_yields_nothing_rather_than_an_error(key):
    """Falling through to the key path is correct: an invalid assertion is not a
    reason to refuse a caller who also holds a valid key."""
    ident = _identity(key)
    req = _Req({"cf-access-jwt-assertion": _token(_key())})
    assert ident.caller(req, NU) is None


def test_the_keys_are_cached_and_refreshed(key):
    from wordsworth.access_identity import Identity

    opgehaald = []

    def fetch(url):
        opgehaald.append(url)
        return _jwks(key)

    ident = Identity(VERIFIER, fetch=fetch, ttl=100)
    req = _Req({"cf-access-jwt-assertion": _token(key)})
    for _ in range(3):
        ident.caller(req, NU)
    assert len(opgehaald) == 1
    ident.caller(req, NU + 101)          # past the ttl
    assert len(opgehaald) == 2


def test_a_failed_refresh_keeps_the_keys_we_have(key):
    """Locking everyone out over a network hiccup is the wrong failure; an
    assertion we can still verify is not less trustworthy for it."""
    from wordsworth.access_identity import Identity

    beurt = {"n": 0}

    def fetch(url):
        beurt["n"] += 1
        if beurt["n"] > 1:
            raise ConnectionError("weg")
        return _jwks(key)

    ident = Identity(VERIFIER, fetch=fetch, ttl=10)
    req = _Req({"cf-access-jwt-assertion": _token(key)})
    assert ident.caller(req, NU) == "mark@westerweel.work"
    assert ident.caller(req, NU + 50) == "mark@westerweel.work"


def test_without_any_keys_every_assertion_is_refused(key):
    from wordsworth.access_identity import Identity

    def fetch(url):
        raise ConnectionError("nooit bereikbaar")

    ident = Identity(VERIFIER, fetch=fetch)
    req = _Req({"cf-access-jwt-assertion": _token(key)})
    assert ident.caller(req, NU) is None


# --- a credential you send beats one that rides along ----------------------

def test_a_presented_key_wins_over_an_injected_assertion(session_factory, key):
    """An identity provider injects its assertion on every request through it.
    Without this order, someone behind that provider could never be anything
    else, and the way back to a key would exist only on routes that bypass the
    provider — which is exactly where Mark could not reach."""
    from fastapi.testclient import TestClient

    from wordsworth.api import create_app
    from wordsworth.search_index import InMemoryIndex

    class _Ident:
        def caller(self, request, now=None):
            from wordsworth.access_identity import public_keys
            tok = request.headers.get("cf-access-jwt-assertion", "")
            if not tok:
                return None
            try:
                return email_from(tok, public_keys(VERIFIER, lambda u: _jwks(key)),
                                  VERIFIER, NU)
            except Exception:
                return None

    index = InMemoryIndex()
    index.index("a", "vergunning", "ka")
    app = create_app(session_factory=session_factory, api_keys={"k": "cli"},
                     search_index=index)
    for m in app.user_middleware:
        if m.cls.__name__ == "ApiKeyAuthMiddleware":
            m.kwargs["identity"] = _Ident()
    c = TestClient(app)

    beide = {"X-API-Key": "k", "cf-access-jwt-assertion": _token(key)}
    r = c.get("/search", params={"q": "vergunning", "dossier": "alle"},
              headers=beide)
    assert r.status_code == 200          # the key was accepted
    # and with only the assertion, the identity still works
    alleen = {"cf-access-jwt-assertion": _token(key)}
    assert c.get("/search", params={"q": "vergunning", "dossier": "alle"},
                 headers=alleen).status_code == 200
    # and with neither, nothing
    assert c.get("/search", params={"q": "vergunning", "dossier": "alle"}
                 ).status_code == 401


def test_the_key_form_stays_reachable_from_behind_a_provider(session_factory, key):
    """A way back has to exist on the route people actually use.

    Behind a provider the assertion rides along on every request, so without
    this door a person there could never choose the key — and the alternative
    routes are exactly the ones Mark could not reach."""
    from fastapi.testclient import TestClient

    from wordsworth.api import create_app

    class _Ident:
        def caller(self, request, now=None):
            return "mark@westerweel.work" if request.headers.get(
                "cf-access-jwt-assertion") else None

    app = create_app(session_factory=session_factory, api_keys={"k": "console"})
    for m in app.user_middleware:
        if m.cls.__name__ == "ApiKeyAuthMiddleware":
            m.kwargs["identity"] = _Ident()
    c = TestClient(app, follow_redirects=False,
                      base_url="https://testserver")
    h = {"cf-access-jwt-assertion": "iets"}
    vraag = c.get("/console/login", headers=h)
    assert vraag.status_code == 200 and "API-sleutel" in vraag.text
    # and logging in there takes precedence over the assertion
    r = c.post("/console/login", data={"key": "k"}, headers=h)
    assert r.status_code == 303 and "ww_console" in r.headers["set-cookie"]
