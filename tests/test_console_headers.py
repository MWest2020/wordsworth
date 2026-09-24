# SPDX-License-Identifier: MIT
"""Wat de browser van de console mag maken (securityreview 18-09)."""
from fastapi.testclient import TestClient

from wordsworth.api import create_app
from wordsworth.console_headers import same_origin


def _app(session_factory):
    return TestClient(create_app(session_factory=session_factory,
                                 api_keys={"k": "mark"}),
                      base_url="https://testserver", follow_redirects=False)


def test_the_console_cannot_be_framed(session_factory):
    """Zonder dit kan iemand /console/documents/<id> in een onzichtbare iframe
    zetten en de Onthul-knop onder een cursor schuiven. Hij leest het antwoord
    niet — CORS staat dicht — maar de onthulling gebeurt, en het auditspoor
    noemt het slachtoffer. Dat is niet te repareren."""
    r = _app(session_factory).get("/console/login")
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "no-referrer"


def test_the_api_itself_is_untouched(session_factory):
    """Alleen /console. De API heeft geen browser en zou van een CSP alleen
    maar verrassingen krijgen."""
    r = _app(session_factory).get("/health")
    assert "content-security-policy" not in r.headers


def test_a_cross_site_post_is_refused(session_factory):
    """Login-CSRF: een pagina elders kan anders het callerlabel van een bezoeker
    wisselen naar een sleutel die de aanvaller kent. Geen rechtenverhoging, wel
    valse attributie in een append-only spoor."""
    c = _app(session_factory)
    r = c.post("/console/login", data={"key": "k"},
               headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    assert "set-cookie" not in {h.lower() for h in r.headers}


def test_a_same_site_post_still_works(session_factory):
    c = _app(session_factory)
    r = c.post("/console/login", data={"key": "k"},
               headers={"Origin": "https://testserver"})
    assert r.status_code == 303


def test_a_request_without_an_origin_is_allowed(session_factory):
    """curl, de CLI en de tests sturen geen Origin. Die buitensluiten zou de
    verdediging duurder maken dan het gat."""
    assert _app(session_factory).post("/console/login",
                                      data={"key": "k"}).status_code == 303


def test_the_origin_check_is_explicit_about_its_limits():
    assert same_origin("", "wat dan ook") is True
    assert same_origin("https://evil.example", "wordsworth.westerweel.work") is False
    assert same_origin("https://wordsworth.westerweel.work",
                       "wordsworth.westerweel.work:443") is True


def test_an_origin_matches_only_its_own_host_and_port():
    """Exact since 2026-09-24. The suffix check it replaces let any hostname
    ending in ours through, and refused every Origin that carried a port."""
    # Production, both routes: public name, and the tailnet name.
    assert same_origin("https://wordsworth.westerweel.work", "wordsworth.westerweel.work")
    assert same_origin("https://wordsworth-api.tail8f7877.ts.net",
                       "wordsworth-api.tail8f7877.ts.net")
    # Local development: the Origin carries the port, and now matches.
    assert same_origin("http://localhost:8000", "localhost:8000")
    assert same_origin("http://127.0.0.1:8000", "127.0.0.1:8000")
    # Case is not identity.
    assert same_origin("https://Wordsworth.Westerweel.Work", "wordsworth.westerweel.work")


def test_a_lookalike_origin_is_refused():
    host = "wordsworth.westerweel.work"
    assert not same_origin("https://evilwordsworth.westerweel.work", host)
    assert not same_origin("https://x.evil.example/wordsworth.westerweel.work", host)
    assert not same_origin("https://wordsworth.westerweel.work.evil.example", host)


def test_another_port_or_an_opaque_origin_is_refused():
    assert not same_origin("http://localhost:9999", "localhost:8000")
    assert not same_origin("http://wordsworth.westerweel.work",
                           "wordsworth.westerweel.work:443")
    assert not same_origin("null", "wordsworth.westerweel.work")
    assert not same_origin("file://", "wordsworth.westerweel.work")
    assert not same_origin("https://wordsworth.westerweel.work", "wordsworth.westerweel.work:abc")
