# SPDX-License-Identifier: MIT
"""``email_verified`` through the application (api-corpus-read-gate, task 4):
an OIDC token whose address is not verified names no caller, so it is refused
like no token at all, and a valid key on the same request is that key's
caller. The verifier itself is tested in test_access_identity.py."""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from inventory_app import full_app
from test_access_identity import _jwks, _key, _token
from wordsworth.access_identity import Identity, Verifier

ISSUER = "https://iam.westerweel.work/realms/westerweel"
JWKS = f"{ISSUER}/protocol/openid-connect/certs"


@pytest.fixture(scope="module")
def key():
    return _key()


@pytest.fixture(scope="module")
def client(key):
    verifier = Verifier.oidc(ISSUER, "wordsworth", jwks_url=JWKS)
    app = full_app(access_verifier=verifier,
                   corpus_read_labels=["lezer", "mark@westerweel.work"])
    for m in app.user_middleware:
        if m.cls.__name__ == "ApiKeyAuthMiddleware":    # no network for the keys
            m.kwargs["identity"] = Identity(verifier, fetch=lambda url: _jwks(key))
    return TestClient(app, raise_server_exceptions=False)


def _bearer(key, **claims) -> dict:
    token = _token(key, aud=["wordsworth"], iss=ISSUER, exp=time.time() + 3600,
                   **claims)
    return {"Authorization": f"Bearer {token}"}


def _ranking(client, headers):
    """A corpus-read route whose body runs on the stand-ins (an empty index)."""
    return client.get("/export/ranking.csv", params={"query": "x"},
                      headers=headers).status_code


def test_a_verified_address_on_the_read_list_is_a_reader(client, key):
    assert _ranking(client, _bearer(key, email_verified=True)) == 200


@pytest.mark.parametrize("claim", [False, None, "true", 1],
                         ids=["false", "absent", "string", "one"])
def test_an_unverified_address_names_no_caller(client, key, claim):
    claims = {} if claim is None else {"email_verified": claim}
    assert _ranking(client, _bearer(key, **claims)) == 401


@pytest.mark.parametrize("claim", [False, None])
def test_with_a_valid_key_the_key_is_the_caller(client, key, claim):
    claims = {} if claim is None else {"email_verified": claim}
    headers = _bearer(key, **claims)
    assert _ranking(client, {**headers, "X-API-Key": "klezer"}) == 200   # lezer
    assert _ranking(client, {**headers, "X-API-Key": "kderde"}) == 403   # derde
