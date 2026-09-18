# SPDX-License-Identifier: MIT
"""Who is calling, when an identity provider sits in front (access-identity).

Cloudflare Access puts two things on a request: a readable header naming the
user, and a signed assertion. They arrive together and look equally convincing.
Only one of them cannot be forged.

**The header is never a source. The signature is.** That distinction is the whole
module. Trusting the header would turn every path that does not pass the provider
— the tailnet route, a direct call to the origin — into a way to claim any
identity, and those paths exist. Verifying the signature makes them harmless by
construction: no valid assertion, no identity, fall back to the API key.

Verified with ``cryptography``, which is already a dependency for the key vault.
Checking one RS256 signature is less code than adding a JWT library, and this is
the one place in the system where a subtle "it validated" is worth reading in
full rather than trusting to a package.
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

#: The header Access puts the signed assertion in.
JWT_HEADER = "cf-access-jwt-assertion"
#: The readable one. Named here so it is obvious this module never reads it.
EMAIL_HEADER_NEVER_TRUSTED = "cf-access-authenticated-user-email"


class AccessError(ValueError):
    """An assertion that cannot be trusted. Never a reason to fall back."""


def _b64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


@dataclass(frozen=True)
class Verifier:
    """What it takes to check an assertion: whose keys, and for which app."""

    team_domain: str          # e.g. raspy-wood-e123.cloudflareaccess.com
    audience: str             # the application's own AUD tag

    @property
    def certs_url(self) -> str:
        return f"https://{self.team_domain}/cdn-cgi/access/certs"

    @property
    def issuer(self) -> str:
        return f"https://{self.team_domain}"


def public_keys(verifier: Verifier, fetch=None) -> dict:
    """``kid -> RSAPublicKey`` from the team's published JWKS."""
    raw = (fetch or _fetch)(verifier.certs_url)
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
    """The verified email in this assertion, or raise.

    Every check here is a refusal, never a warning. An assertion that fails any
    of them yields no identity at all — there is no partial trust.
    """
    now = time.time() if now is None else now
    try:
        head_raw, body_raw, sig_raw = token.split(".")
        head = json.loads(_b64(head_raw))
        body = json.loads(_b64(body_raw))
    except Exception as exc:
        # Alles wat hier stukgaat komt van een aanvaller: de header wordt gelezen
        # vóór enige authenticatie, op elk niet-vrijgesteld pad. Een misvormde
        # base64 gooide binascii.Error, dat is géén AccessError, en die liep door
        # de middleware heen naar een 500. Elke misvorming is een weigering.
        raise AccessError(f"not a readable assertion: {type(exc).__name__}")

    if head.get("alg") != "RS256":
        # Refusing anything else is what closes the "alg: none" family of
        # attacks, where the token names its own (absent) verification.
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
        # An assertion for another application of the same organisation is a
        # valid signature and not access to this one.
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
        # Een niet-string zou doorstromen naar het callerlabel en het
        # auditspoor. Dat is niet bereikbaar zonder Cloudflares sleutel, maar
        # "niet bereikbaar" is een slechtere garantie dan "afgewezen".
        raise AccessError("assertion names no usable email")
    return email


class Identity:
    """Resolves a request to a person, or to nothing.

    Holds the public keys and refreshes them on a schedule, because the provider
    rotates them. A failed refresh keeps the keys we have: an assertion signed by
    a key we can still verify is not less trustworthy because a fetch timed out,
    and locking everyone out over a network hiccup is the wrong failure. A key we
    have never seen is refused either way.
    """

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
            # Keep what we have; see the class docstring. If we have nothing,
            # the empty dict refuses every assertion, which is the safe end.
            #
            # En wél het moment onthouden: zonder dat probeerde ELK verzoek het
            # opnieuw, en met een hangend endpoint is dat een blokkerende fetch
            # per verzoek.
            self._at = now - self._ttl + self._backoff
        return self._keys

    def caller(self, request, now: float | None = None):
        """The verified email on this request, or None.

        Never reads the readable email header. That is the entire point: it
        arrives on every path, including the ones that do not pass the provider.
        """
        token = request.headers.get(JWT_HEADER, "")
        if not token:
            return None
        try:
            return email_from(token, self.keys(now), self.verifier, now)
        except AccessError:
            return None
