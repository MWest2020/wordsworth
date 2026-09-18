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
