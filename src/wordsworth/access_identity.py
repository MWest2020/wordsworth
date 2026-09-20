# SPDX-License-Identifier: MIT
"""Who is calling, when an identity provider sits in front (access-identity).

A provider puts two things on a request: a readable header naming the user,
and a signed token. **The header is never a source. The signature is.**
Trusting the header would turn every path that skips the provider — the
tailnet route, a direct call to the origin — into a way to claim any identity.

Any OIDC issuer is checked the same way once issuer, audience and JWKS
address are known: Cloudflare Access (fixed JWKS address) and Keycloak
(discovered from it) both resolve to one `Verifier`, one verification path.
Verified with ``cryptography`` (already a key-vault dependency) rather than
adding a JWT library.
"""
from __future__ import annotations

import base64
import json
import time
import urllib.request
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

JWT_HEADER = "cf-access-jwt-assertion"          # Cloudflare Access: signed assertion
BEARER_HEADER = "authorization"                 # oauth2-proxy, e.g. Keycloak
BEARER_PREFIX = "Bearer "
#: The readable one — named so it is obvious this module never reads it.
EMAIL_HEADER_NEVER_TRUSTED = "cf-access-authenticated-user-email"


class AccessError(ValueError):
    """A token that cannot be trusted. Never a reason to fall back."""


class DiscoveryError(ValueError):
    """An issuer's OIDC discovery document could not be read or used."""


def _b64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


#: issuer -> jwks_uri; a running issuer's address rarely changes, so a plain
#: dict is enough, fetched once instead of per `Verifier.oidc` call.
_discovery_cache: dict[str, str] = {}


def discover_jwks_url(issuer: str, fetch=None) -> str:
    """``jwks_uri`` from ``<issuer>/.well-known/openid-configuration``; unreachable,
    unreadable, or missing ``jwks_uri`` all raise `DiscoveryError`."""
    if issuer in _discovery_cache:
        return _discovery_cache[issuer]
    url = issuer.rstrip("/") + "/.well-known/openid-configuration"
    try:
        doc = (fetch or _fetch)(url)
    except Exception as exc:
        raise DiscoveryError(f"discovery unreachable for issuer {issuer!r}: "
                             f"{type(exc).__name__}") from exc
    jwks_uri = doc.get("jwks_uri") if isinstance(doc, dict) else None
    if not jwks_uri:
        raise DiscoveryError(f"discovery document for issuer {issuer!r} names no jwks_uri")
    _discovery_cache[issuer] = jwks_uri
    return jwks_uri


@dataclass(frozen=True)
class Verifier:
    """What it takes to check a token: whose keys, which issuer, which app."""

    issuer: str      # e.g. https://iam.westerweel.work/realms/westerweel
    audience: str    # the application's own aud/client id
    jwks_url: str    # where the issuer's public keys live

    @classmethod
    def cloudflare(cls, team_domain: str, audience: str) -> "Verifier":
        """e.g. ``team_domain="raspy-wood-e123.cloudflareaccess.com"``; the
        JWKS address is fixed, never discovered."""
        return cls(issuer=f"https://{team_domain}", audience=audience,
                    jwks_url=f"https://{team_domain}/cdn-cgi/access/certs")

    @classmethod
    def oidc(cls, issuer: str, audience: str, fetch=None) -> "Verifier":
        """Any OIDC issuer (Keycloak, ...); the JWKS address is discovered."""
        return cls(issuer=issuer, audience=audience,
                    jwks_url=discover_jwks_url(issuer, fetch=fetch))


def public_keys(verifier: Verifier, fetch=None) -> dict:
    """``kid -> RSAPublicKey`` from the issuer's published JWKS."""
    raw = (fetch or _fetch)(verifier.jwks_url)
    keys = {}
    for k in raw.get("keys", []):
        if k.get("kty") != "RSA":
            continue
        n = int.from_bytes(_b64(k["n"]), "big")
        e = int.from_bytes(_b64(k["e"]), "big")
        keys[k["kid"]] = rsa.RSAPublicNumbers(e, n).public_key()
    return keys


def _fetch(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
        return json.loads(resp.read())


def email_from(token: str, keys: dict, verifier: Verifier, now: float | None = None):
    """The verified email in this assertion, or raise. Every check here is a
    refusal, never a warning — there is no partial trust."""
    now = time.time() if now is None else now
    try:
        head_raw, body_raw, sig_raw = token.split(".")
        head = json.loads(_b64(head_raw))
        body = json.loads(_b64(body_raw))
    except Exception as exc:
        # Everything here comes from an attacker, read before authentication.
        # A malformed base64 used to raise binascii.Error past AccessError
        # into a 500 — every malformation is now a refusal.
        raise AccessError(f"not a readable assertion: {type(exc).__name__}")

    if head.get("alg") != "RS256":
        # Closes the "alg: none" family, where the token names its own
        # (absent) verification.
        raise AccessError(f"unexpected algorithm {head.get('alg')!r}")
    key = keys.get(head.get("kid"))
    if key is None:
        raise AccessError("assertion signed by an unknown key")
    try:
        handtekening = _b64(sig_raw)
    except Exception as exc:
        raise AccessError(f"unreadable signature: {type(exc).__name__}")
    try:
        key.verify(handtekening, f"{head_raw}.{body_raw}".encode(),
                   padding.PKCS1v15(), hashes.SHA256())
    except InvalidSignature:
        raise AccessError("signature does not match")

    aud = body.get("aud")
    aud = aud if isinstance(aud, list) else [aud]
    if verifier.audience not in aud:
        # A valid signature for another application is not access to this one.
        raise AccessError("assertion is for another application")
    if body.get("iss") != verifier.issuer:
        raise AccessError("assertion is from another issuer")
    try:
        verloopt = float(body.get("exp", 0))
    except (TypeError, ValueError):
        raise AccessError("assertion has an unreadable expiry")
    if verloopt <= now:
        raise AccessError("assertion has expired")
    email = body.get("email")
    if not isinstance(email, str) or not email.strip():
        # A non-string would flow into the caller label and the audit trail.
        raise AccessError("assertion names no usable email")
    return email


class Identity:
    """Resolves a request to a person, or to nothing. Refreshes public keys on
    a schedule; a failed refresh keeps what we have rather than locking
    everyone out over a network hiccup. A key never seen is refused either way."""

    def __init__(self, verifier: Verifier, fetch=None, ttl: float = 900.0,
                 backoff: float = 30.0) -> None:
        self.verifier = verifier
        self._fetch = fetch or _fetch
        self._ttl = ttl
        #: Hoe lang na een mislukte verversing we het niet opnieuw proberen.
        self._backoff = backoff
        self._keys: dict = {}
        self._at = 0.0

    def keys(self, now: float | None = None) -> dict:
        now = time.time() if now is None else now
        if self._keys and now - self._at < self._ttl:
            return self._keys
        try:
            self._keys = public_keys(self.verifier, self._fetch)
            self._at = now
        except Exception:
            # Keep what we have (see class docstring); remember the attempt
            # regardless, or a hanging endpoint blocks on every request.
            self._at = now - self._ttl + self._backoff
        return self._keys

    def caller(self, request, now: float | None = None):
        """The verified email on this request, or None. Never reads the
        readable email header: it arrives on every path, including ones
        that skip the provider."""
        auth = request.headers.get(BEARER_HEADER, "")
        token = (auth[len(BEARER_PREFIX):].strip() if auth.startswith(BEARER_PREFIX)
                 else request.headers.get(JWT_HEADER, ""))
        if not token:
            return None
        try:
            return email_from(token, self.keys(now), self.verifier, now)
        except AccessError:
            return None
