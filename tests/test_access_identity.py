# SPDX-License-Identifier: MIT
"""Verifying who is calling when a provider sits in front (access-identity).

Signed with real RSA keys, not with a stub that says "valid". The whole point of
this module is that a signature cannot be forged, and a test double that simply
returns True would prove nothing about that. No network: every fetch (JWKS,
OIDC discovery) is injected.
"""
import base64
import json

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from wordsworth.access_identity import (AccessError, DiscoveryError, Verifier,
                                        discover_jwks_url, email_from,
                                        public_keys)

TEAM = "raspy-wood-e123.cloudflareaccess.com"
AUD = "320841be57b2e469adbef09614573240756da5f3a188df87b6fb761d40e65d65"
VERIFIER = Verifier.cloudflare(TEAM, AUD)
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
    body = {"aud": [AUD], "iss": VERIFIER.issuer, "exp": NU + 3600,
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


def test_a_valid_assertion_yields_the_email(key, keys):
    assert email_from(_token(key), keys, VERIFIER, NU) == "mark@westerweel.work"


def test_the_cloudflare_variant_builds_a_fixed_issuer_and_jwks_url(key):
    """One way to build a `Verifier`: no separate code path for Cloudflare."""
    assert VERIFIER.issuer == f"https://{TEAM}"
    assert VERIFIER.jwks_url == f"https://{TEAM}/cdn-cgi/access/certs"
    assert VERIFIER.audience == AUD


def test_a_signature_from_another_key_is_refused(keys):
    """The heart of it: an attacker who can set headers cannot make this pass."""
    with pytest.raises(AccessError, match="signature"):
        email_from(_token(_key()), keys, VERIFIER, NU)


def test_a_tampered_payload_is_refused(key, keys):
    """Changing the email after signing must invalidate the signature."""
    head, payload, sig = _token(key).split(".")
    body = json.loads(base64.urlsafe_b64decode(payload + "=="))
    body["email"] = "iemand.anders@example.com"
    vervalst = f"{head}.{_b64(json.dumps(body).encode())}.{sig}"
    with pytest.raises(AccessError, match="signature"):
        email_from(vervalst, keys, VERIFIER, NU)


def test_an_unsigned_assertion_is_refused(key, keys):
    """`alg: none` names its own absent verification; refusing anything but
    RS256 closes that whole family."""
    head = _b64(json.dumps({"alg": "none", "kid": "k1"}).encode())
    payload = _b64(json.dumps({"email": "x@y.nl", "aud": [AUD]}).encode())
    with pytest.raises(AccessError, match="algorithm"):
        email_from(f"{head}.{payload}.", keys, VERIFIER, NU)


def test_an_assertion_for_another_application_is_refused(key, keys):
    """A valid signature from the same organisation is not access to this app."""
    with pytest.raises(AccessError, match="another application"):
        email_from(_token(key, aud=["een-andere-app"]), keys, VERIFIER, NU)


def test_an_assertion_from_another_issuer_is_refused(key, keys):
    with pytest.raises(AccessError, match="another issuer"):
        email_from(_token(key, iss="https://kwaadaardig.example"), keys, VERIFIER, NU)


def test_an_expired_assertion_is_refused(key, keys):
    with pytest.raises(AccessError, match="expired"):
        email_from(_token(key, exp=NU - 1), keys, VERIFIER, NU)


def test_an_assertion_signed_by_an_unknown_key_is_refused(key):
    ander = public_keys(VERIFIER, fetch=lambda url: _jwks(_key(), kid="anders"))
    with pytest.raises(AccessError, match="unknown key"):
        email_from(_token(key), ander, VERIFIER, NU)


def test_an_assertion_without_an_email_is_refused(key, keys):
    with pytest.raises(AccessError, match="no usable email"):
        email_from(_token(key, email=""), keys, VERIFIER, NU)


def test_rubbish_is_refused_without_crashing(keys):
    for rommel in ["", "geen punt", "a.b", "a.b.c", "...."]:
        with pytest.raises(AccessError):
            email_from(rommel, keys, VERIFIER, NU)


def test_a_single_audience_string_is_accepted(key, keys):
    """Some issuers write aud as a string rather than a list."""
    assert email_from(_token(key, aud=AUD), keys, VERIFIER, NU)


# --- OIDC discovery: how a Keycloak-style Verifier gets its JWKS address ---

def test_oidc_discovery_resolves_the_jwks_url_from_the_issuer():
    issuer = "https://iam.westerweel.work/realms/westerweel-1"
    jwks_uri = f"{issuer}/protocol/openid-connect/certs"
    v = Verifier.oidc(issuer, "wordsworth",
                      fetch=lambda url: {"jwks_uri": jwks_uri})
    assert v.issuer == issuer
    assert v.audience == "wordsworth"
    assert v.jwks_url == jwks_uri


def test_oidc_discovery_is_fetched_once_and_cached():
    issuer = "https://iam.westerweel.work/realms/westerweel-2"
    calls = []

    def fetch(url):
        calls.append(url)
        return {"jwks_uri": f"{issuer}/protocol/openid-connect/certs"}

    discover_jwks_url(issuer, fetch=fetch)
    discover_jwks_url(issuer, fetch=fetch)
    assert len(calls) == 1


def test_an_unreachable_discovery_document_is_a_clean_error():
    def fetch(url):
        raise ConnectionError("onbereikbaar")

    with pytest.raises(DiscoveryError, match="unreachable"):
        discover_jwks_url("https://iam.westerweel.work/realms/onbereikbaar",
                          fetch=fetch)


def test_a_discovery_document_without_jwks_uri_is_a_clean_error():
    with pytest.raises(DiscoveryError, match="jwks_uri"):
        discover_jwks_url("https://iam.westerweel.work/realms/kapot",
                          fetch=lambda url: {"issuer": "iets, geen jwks_uri"})


def test_a_valid_keycloak_style_token_yields_the_email(key):
    """The full OIDC path: discovery, then the same signature check as
    Cloudflare Access gets."""
    issuer = "https://iam.westerweel.work/realms/westerweel-3"
    jwks_uri = f"{issuer}/protocol/openid-connect/certs"

    def fetch(url):
        if url == jwks_uri:
            return _jwks(key)
        return {"jwks_uri": jwks_uri}

    verifier = Verifier.oidc(issuer, "wordsworth", fetch=fetch)
    keys = public_keys(verifier, fetch=fetch)
    token = _token(key, aud=["wordsworth"], iss=issuer)
    assert email_from(token, keys, verifier, NU) == "mark@westerweel.work"
