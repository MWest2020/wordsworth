# SPDX-License-Identifier: MIT
"""Een onbekend pad is iets anders dan een onbekend document (codereview 18-09).

De handler ving élke HTTPException(404), dus ook "unknown document" en "unknown
grant". Die verdwenen voor iedereen met een HTML-Accept achter een omleiding
naar de console: een mens zag nooit dat het document niet bestond, en een
controle op een document-URL las de 303 als gezond.

De spec zei al "a path that matches no route". De implementatie was breder.
"""
from uuid import uuid4

from fastapi.testclient import TestClient

from wordsworth.api import create_app
from wordsworth.search_index import InMemoryIndex

HTML = {"Accept": "text/html"}


def _app(session_factory):
    return TestClient(create_app(session_factory=session_factory,
                                 api_keys={"k": "mark"},
                                 search_index=InMemoryIndex()),
                      base_url="https://testserver", follow_redirects=False)


def test_a_path_that_matches_nothing_sends_a_browser_to_the_console(session_factory):
    c = _app(session_factory)
    c.post("/console/login", data={"key": "k"})
    r = c.get("/dit-pad-bestaat-niet", headers=HTML)
    assert r.status_code == 303 and r.headers["location"] == "/console"


def test_an_unknown_document_stays_a_404_even_for_a_browser(session_factory):
    """Dit is een antwoord over iets wat je vroeg. Wegmoffelen achter een
    omleiding maakt "bestaat niet" onzichtbaar."""
    c = _app(session_factory)
    c.post("/console/login", data={"key": "k"})
    r = c.get(f"/documents/{uuid4()}/state", headers=HTML)
    assert r.status_code == 404, r.headers.get("location")
    assert r.json()["detail"]


def test_an_api_client_keeps_its_404_either_way(session_factory):
    c = _app(session_factory)
    c.post("/console/login", data={"key": "k"})
    for pad in ("/dit-pad-bestaat-niet", f"/documents/{uuid4()}/state"):
        assert c.get(pad, headers={"Accept": "*/*"}).status_code == 404, pad
