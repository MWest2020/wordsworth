# SPDX-License-Identifier: MIT
"""Een 403 op een browserpad is een pagina, geen kale JSON.

Op 2026-09-19 opende Mark `/console/topics` en kreeg letterlijk
`{"detail":"caller not authorized for corpus read"}` op een witte pagina. De
aanmelding was gelukt; alleen stond zijn naam niet op de corpus-leeslijst, die
nog uit het tijdperk van de api-sleutels kwam.

Dat is de 401-les op een andere as. Een 401 kan naar de inlogpagina; een 403
niet — hij ís ingelogd, dus dat zou een lus zijn. Er hoort een pagina te staan
die zegt ónder welke naam hij binnenkwam, anders weet niemand welke naam er dan
wél op de lijst moet.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from wordsworth.api import create_app

KEYS = {"s3cret": "mark", "andere": "iemand-anders"}


def _client(session_factory):
    return TestClient(
        create_app(session_factory=session_factory, api_keys=KEYS,
                   corpus_read_labels=["console"]),   # "mark" staat er niet op
        base_url="https://testserver")


def test_a_browser_gets_a_page_that_names_the_caller(session_factory):
    c = _client(session_factory)
    c.post("/console/login", data={"key": "s3cret"})
    r = c.get("/console", headers={"Accept": "text/html"})
    assert r.status_code == 403
    assert "<h1>" in r.text, "dit hoort een pagina te zijn"
    assert "mark" in r.text, "zonder de naam weet niemand wat er op de lijst moet"
    assert "WORDSWORTH_CORPUS_READ_LABELS" in r.text, "zeg wat eraan te doen is"


def test_the_page_does_not_reveal_who_is_on_the_list(session_factory):
    """Wie er wél mag lezen is precies wat je niet hoort te weten als je er niet
    bij hoort."""
    c = _client(session_factory)
    c.post("/console/login", data={"key": "s3cret"})
    r = c.get("/console", headers={"Accept": "text/html"})
    assert "console" not in r.text.replace("/console", "").replace(
        "console-static", ""), "de lijst zelf hoort er niet in te staan"


def test_an_api_client_keeps_its_json(session_factory):
    """Alleen een browsernavigatie krijgt de pagina. Een client die geen HTML
    vraagt hoort zijn machineleesbare fout te houden."""
    from uuid import uuid4

    c = _client(session_factory)
    # Een gescoped leespad dat de corpus-poort passeert. Dat het document niet
    # bestaat maakt niet uit: de poort staat ervóór, en dat is juist -- anders
    # zou het bestaan van een document uit de foutcode af te leiden zijn.
    r = c.get(f"/documents/{uuid4()}/anonymized",
              headers={"Accept": "application/json", "x-api-key": "s3cret"})
    assert r.status_code == 403
    assert r.json()["detail"]
    assert "<h1>" not in r.text


def test_the_topics_page_is_the_one_that_broke(session_factory):
    c = _client(session_factory)
    c.post("/console/login", data={"key": "s3cret"})
    r = c.get("/console/topics", headers={"Accept": "text/html"})
    assert r.status_code == 403
    assert "<h1>" in r.text
