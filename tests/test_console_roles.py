# SPDX-License-Identifier: MIT
"""De rollenpagina in de console (rollen)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from wordsworth.api import create_app

# sleutel -> label (zo leest create_app het)
KEYS = {"sk-beheer": "beheer", "sk-lezer": "lezer"}


def _client(session_factory, sleutel="sk-beheer"):
    app = create_app(session_factory=session_factory, api_keys=KEYS,
                     grant_issuer_labels=["beheer"])
    c = TestClient(app, base_url="https://testserver")
    c.post("/console/login", data={"key": sleutel})
    return c


def test_the_page_offers_the_types_the_system_knows(session_factory):
    """De aanvinklijst komt uit het typeregister. Een eigen lijstje in de
    template zou op een dag stilletjes verschillen van wat het systeem kent."""
    r = _client(session_factory).get("/console/roles")
    assert r.status_code == 200
    for t in ("PERSON", "BSN", "GEZONDHEID", "STRAFRECHTELIJK"):
        assert t in r.text
    # En de AVG-grondslag erbij, want c1 en c2 zijn niet dezelfde beslissing.
    assert "Art. 9" in r.text


def test_creating_a_role_from_the_page(session_factory):
    c = _client(session_factory)
    r = c.post("/console/roles", data={"name": "HR", "types": ["PERSON", "EMAIL"]},
               follow_redirects=False)
    assert r.status_code == 303, "redirect-na-post, anders maakt herladen hem opnieuw"
    pagina = c.get("/console/roles").text
    assert "HR" in pagina and "PERSON" in pagina and "actief" in pagina


def test_switching_off_from_the_page_needs_a_reason(session_factory):
    c = _client(session_factory)
    c.post("/console/roles", data={"name": "HR", "types": ["PERSON"]})
    r = c.post("/console/roles/switch",
               data={"name": "HR", "aan": "0", "reason": ""})
    assert "reden" in r.text.lower()
    assert "actief" in c.get("/console/roles").text

    c.post("/console/roles/switch",
           data={"name": "HR", "aan": "0", "reason": "sleutel gelekt"})
    assert "UIT" in c.get("/console/roles").text


def test_the_page_is_behind_the_admin_gate_not_the_read_gate(session_factory):
    """Rollen bepalen wat iedereen met die rol mag zien. Stond deze pagina
    achter de léés-poort, dan was het een scherm waarmee een lezer zijn eigen
    rechten kan verruimen — de tweede deur, met een vriendelijker naam."""
    c = _client(session_factory, sleutel="sk-lezer")
    assert c.get("/console/roles").status_code == 403
    assert c.post("/console/roles",
                  data={"name": "x", "types": []}).status_code == 403
    assert c.post("/console/roles/switch",
                  data={"name": "x", "aan": "0", "reason": "y"}).status_code == 403


def test_a_duplicate_name_says_so_on_the_page(session_factory):
    c = _client(session_factory)
    c.post("/console/roles", data={"name": "HR", "types": ["PERSON"]})
    r = c.post("/console/roles", data={"name": "HR", "types": ["BSN"]})
    assert "bestaat al" in r.text
