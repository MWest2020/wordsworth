# SPDX-License-Identifier: MIT
"""Waar de authenticatie iets beweerde dat ze niet deed (securityreview 18-09).

Vier bevindingen, elk met een test die zonder de reparatie faalt. Ze delen één
vorm: er stond een geruststelling in een commentaar of een docstring, en de code
maakte hem niet waar. Dat is erger dan het gat zelf — wie de regel leest, kijkt
niet verder.
"""
import pytest
from fastapi.testclient import TestClient

from wordsworth.api import create_app
from wordsworth.search_index import InMemoryIndex


class _Ident:
    """Een identiteitsprovider die iedereen met de header binnenlaat."""

    def caller(self, request, now=None):
        return request.headers.get("x-wie") or None


# --- S1: de recipient-binding viel stil zodra er geen sleutels waren ---------

def test_identity_only_keeps_the_recipient_binding_on(session_factory):
    """`auth_enabled = bool(keys)` bewoog niet mee met waarop de middleware
    mount. Een installatie met alléén een identiteitsprovider was dus
    geauthenticeerd terwijl elke grant weer een bearer-token was."""
    from wordsworth.grants import InMemoryGrantStore
    from wordsworth.keys import InMemoryKeyProvider
    from wordsworth.pipeline import register

    with session_factory() as s:
        doc = register(s, "documents/aa")
        s.commit()
        doc_id = doc.id
    gs = InMemoryGrantStore()
    grant = gs.issue("iemand-anders", ["PERSON"], actor="mark", document_id=doc_id)

    app = create_app(session_factory=session_factory, api_keys={},
                     key_provider=InMemoryKeyProvider(), grant_store=gs,
                     access_verifier=object())
    for m in app.user_middleware:
        if m.cls.__name__ == "ApiKeyAuthMiddleware":
            m.kwargs["identity"] = _Ident()
    c = TestClient(app)
    r = c.post(f"/documents/{doc_id}/reveal", json={"grant_id": grant.grant_id},
               headers={"x-wie": "aanvaller@example.org"})
    assert r.status_code == 403, "een grant van iemand anders mag niets onthullen"


def test_identity_only_keeps_the_issuer_scope_on(session_factory):
    """Zelfde oorzaak: iedere ingelogde persoon mocht grants minten."""
    from wordsworth.grants import InMemoryGrantStore
    from wordsworth.keys import InMemoryKeyProvider
    from wordsworth.pipeline import register

    with session_factory() as s:
        doc = register(s, "documents/aa")
        s.commit()
        doc_id = doc.id
    app = create_app(session_factory=session_factory, api_keys={},
                     key_provider=InMemoryKeyProvider(),
                     grant_store=InMemoryGrantStore(),
                     grant_issuer_labels=["alleen-ops"],
                     access_verifier=object())
    for m in app.user_middleware:
        if m.cls.__name__ == "ApiKeyAuthMiddleware":
            m.kwargs["identity"] = _Ident()
    r = TestClient(app).post("/grants", json={
        "recipient": "aanvaller", "allowed_types": ["BSN"],
        "document_id": str(doc_id)}, headers={"x-wie": "aanvaller@example.org"})
    assert r.status_code == 403


# --- S3: een misvormde assertie is een weigering, geen 500 ------------------

@pytest.mark.parametrize("rommel", ["a.b.a", "x", "a.b.c.d", "..", "A.B.A"])
def test_a_malformed_assertion_never_crashes(rommel):
    """Dit pad ligt vóór de authenticatie, op elk niet-vrijgesteld pad. Een
    misvormde base64 gooide binascii.Error, dat is geen AccessError, en die liep
    door de middleware heen naar een 500."""
    from wordsworth.access_identity import AccessError, Verifier, email_from

    with pytest.raises(AccessError):
        email_from(rommel, {}, Verifier("t.example", "aud", "t.example/certs"), 0)


def test_an_unreadable_expiry_or_email_is_refused():
    from wordsworth.access_identity import AccessError, Verifier, email_from

    with pytest.raises(AccessError):
        email_from("x.y.z", {}, Verifier("t.example", "aud", "t.example/certs"), 0)


# --- S2: het inlogluik is nu wél gelimiteerd --------------------------------

def test_the_login_path_has_a_limiter():
    """`api.py` zei letterlijk "it stays subject to rate limiting, because that
    is the one path worth guessing at". Dat was onwaar: twaalf pogingen gaven
    twaalf keer 401 en geen enkele 429."""
    from wordsworth.config import settings
    from wordsworth.rate_limit import limiters_from_settings

    assert "/console/login" in limiters_from_settings(settings)


def test_guessing_the_key_runs_out_of_attempts(session_factory):
    c = TestClient(create_app(session_factory=session_factory,
                              api_keys={"goed": "mark"}),
                   base_url="https://testserver", follow_redirects=False)
    codes = [c.post("/console/login", data={"key": f"fout{i}"}).status_code
             for i in range(12)]
    assert 429 in codes, codes
    assert codes.count(401) <= 6          # burst, niet eindeloos


# --- S5: de console gaat niet meer om de corpuspoort heen -------------------

def test_the_console_obeys_the_same_corpus_gate(session_factory):
    """`/documents/{id}/anonymized` gaf 403 en `/console/documents/{id}` gaf
    dezelfde tekst gewoon vrij. Dezelfde gegevens, dezelfde grens."""
    from wordsworth.models import DocumentText
    from wordsworth.pipeline import register

    with session_factory() as s:
        doc = register(s, "documents/aa", filename="a.pdf")
        s.merge(DocumentText(document_id=doc.id, anonymized_text="tekst"))
        s.commit()
        doc_id = doc.id
    c = TestClient(create_app(session_factory=session_factory,
                              api_keys={"k": "kijker"},
                              search_index=InMemoryIndex(),
                              corpus_read_labels=["leesbaar"]),
                   base_url="https://testserver", follow_redirects=False)
    c.post("/console/login", data={"key": "k"})
    for pad in ("/console", f"/console/documents/{doc_id}", "/console/search"):
        assert c.get(pad).status_code == 403, pad


# --- S7: de cookie draagt de sleutel, dus Secure ---------------------------

def test_the_cookie_is_secure(session_factory):
    c = TestClient(create_app(session_factory=session_factory,
                              api_keys={"k": "mark"}),
                   base_url="https://testserver", follow_redirects=False)
    r = c.post("/console/login", data={"key": "k"})
    cookie = r.headers["set-cookie"]
    assert "Secure" in cookie and "HttpOnly" in cookie and "strict" in cookie.lower()
