# SPDX-License-Identifier: MIT
"""The reading console (document-console)."""
import json

from fastapi.testclient import TestClient
from sqlalchemy import select

from wordsworth import pseudonym_registry
from wordsworth.api import create_app
from wordsworth.console import marked
from wordsworth.models import DeclaredCombination, DocumentText
from wordsworth.pipeline import register

KEYS = {"s3cret": "mark"}


def _app(session_factory, keys=KEYS):
    return TestClient(create_app(session_factory=session_factory, api_keys=keys),
                      follow_redirects=False)


def _seed(session, key, text):
    d = register(session, key)
    session.merge(DocumentText(document_id=d.id, anonymized_text=text))
    pseudonym_registry.register(session, d.id, text)
    session.commit()
    return d


def test_marked_splits_text_into_plain_runs_and_typed_tokens():
    parts = marked("Aan [PERSON:aabbccdd] te [POSTCODE:11223344].")
    assert [p["type"] for p in parts] == [None, "PERSON", None, "POSTCODE", None]
    assert "".join(p["text"] for p in parts) == "Aan [PERSON:aabbccdd] te [POSTCODE:11223344]."


def test_marked_handles_text_without_tokens_and_empty_text():
    assert [p["text"] for p in marked("niets")] == ["niets"]
    assert marked("") == [] and marked(None) == []


def test_the_console_is_absent_without_authentication(session_factory):
    """No screen beats a screen without a lock."""
    c = _app(session_factory, keys={})
    assert c.get("/console").status_code == 404
    assert c.get("/console/combinations").status_code == 404


def test_the_console_needs_a_key(session_factory):
    c = _app(session_factory)
    assert c.get("/console").status_code == 401
    assert c.get("/console/login").status_code == 200   # the page that asks


def test_logging_in_sets_an_httponly_cookie_and_the_list_renders(session_factory):
    with session_factory() as s:
        _seed(s, "besluit-1.pdf", "Aan [PERSON:aabbccdd], bsn [BSN:11223344].")
    c = _app(session_factory)
    r = c.post("/console/login", data={"key": "s3cret"})
    assert r.status_code == 303 and r.headers["location"] == "/console"
    cookie = r.headers["set-cookie"]
    assert "HttpOnly" in cookie and "s3cret" in cookie and "strict" in cookie.lower()
    page = c.get("/console")
    assert page.status_code == 200
    assert "besluit-1.pdf" in page.text and "PERSON" in page.text and "BSN" in page.text
    assert "mark" in page.text                       # the caller label, from the key


def test_a_document_page_shows_the_artefact_and_marks_its_tokens(session_factory):
    with session_factory() as s:
        d = _seed(s, "besluit-2.pdf", "Betreft [PERSON:aabbccdd] te [POSTCODE:11223344].")
    c = _app(session_factory)
    c.post("/console/login", data={"key": "s3cret"})
    page = c.get(f"/console/documents/{d.id}")
    assert page.status_code == 200
    assert '<span class="tok" title="PERSON">[PERSON:aabbccdd]</span>' in page.text
    # and it says, on the page, that the original is not here
    assert "reveal" in page.text


def test_a_document_without_stored_text_says_so_instead_of_rendering_nothing(
        session_factory):
    with session_factory() as s:
        d = register(s, "leeg.pdf")
        s.commit()
    c = _app(session_factory)
    c.post("/console/login", data={"key": "s3cret"})
    page = c.get(f"/console/documents/{d.id}")
    assert page.status_code == 200 and "Geen gepseudonimiseerde tekst" in page.text


def test_declaring_a_combination_stores_it_and_shows_its_reach(session_factory):
    with session_factory() as s:
        _seed(s, "a.pdf", "[BSN:aabbccdd] en [POSTCODE:11223344]")
        _seed(s, "b.pdf", "[BSN:eeff0011] alleen")
    c = _app(session_factory)
    c.post("/console/login", data={"key": "s3cret"})
    r = c.post("/console/combinations",
               data={"types": "bsn, postcode", "reason": "samen een persoon en een adres"})
    assert r.status_code == 303
    page = c.get("/console/combinations")
    assert "BSN + POSTCODE" in page.text and "samen een persoon en een adres" in page.text
    with session_factory() as s:
        row = s.execute(select(DeclaredCombination)).scalar_one()
        assert row.types == "BSN+POSTCODE" and row.declared_by == "mark"
    # the reach is the number of documents carrying EVERY type: one of the two
    assert ">1<" in page.text.replace(" ", "").replace("\n", "")


def test_a_combination_without_a_reason_is_refused_and_stores_nothing(session_factory):
    c = _app(session_factory)
    c.post("/console/login", data={"key": "s3cret"})
    r = c.post("/console/combinations", data={"types": "BSN, POSTCODE", "reason": "   "})
    assert r.status_code == 303 and "fout=" in r.headers["location"]
    with session_factory() as s:
        assert s.execute(select(DeclaredCombination)).first() is None


def test_a_single_type_is_not_a_combination(session_factory):
    c = _app(session_factory)
    c.post("/console/login", data={"key": "s3cret"})
    r = c.post("/console/combinations", data={"types": "BSN", "reason": "op zichzelf"})
    assert "fout=" in r.headers["location"]
    with session_factory() as s:
        assert s.execute(select(DeclaredCombination)).first() is None


def test_the_document_page_separates_carried_from_untouched_combinations(session_factory):
    with session_factory() as s:
        d = _seed(s, "c.pdf", "[BSN:aabbccdd] en [POSTCODE:11223344]")
        s.merge(DeclaredCombination(types="BSN+POSTCODE", reason="draagt hij",
                                    declared_by="mark"))
        s.merge(DeclaredCombination(types="EMAIL+IBAN", reason="raakt hij niet",
                                    declared_by="mark"))
        s.commit()
    c = _app(session_factory)
    c.post("/console/login", data={"key": "s3cret"})
    page = c.get(f"/console/documents/{d.id}").text
    assert "draagt hij" in page and "raakt hij niet" in page
    assert page.index("Draagt deze combinaties") < page.index("Onaangeroerd")


def test_an_injected_script_in_a_document_is_escaped(session_factory):
    """Autoescaping, checked rather than assumed: the text is a government
    document and nobody guarantees what is in it."""
    with session_factory() as s:
        d = _seed(s, "<img src=x onerror=alert(1)>", "<script>alert(1)</script> [BSN:aabbccdd]")
    c = _app(session_factory)
    c.post("/console/login", data={"key": "s3cret"})
    page = c.get(f"/console/documents/{d.id}").text
    assert "<script>alert(1)</script>" not in page and "&lt;script&gt;" in page
    assert "<img src=x onerror=alert(1)>" not in c.get("/console").text
