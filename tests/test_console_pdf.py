# SPDX-License-Identifier: MIT
"""The PDF views on the console document page (console-pdf-views).

DB-backed: runs against a real Postgres and skips locally without one."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from wordsworth import console_pdf, pseudonym_registry
from wordsworth.api import create_app
from wordsworth.grants import InMemoryGrantStore
from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.models import BoxMap, DocumentText, GrantRecord
from wordsworth.pipeline import ingest, process, register
from wordsworth.pseudonymizer import Pseudonymizer

KEYS = {"k-mark": "mark", "k-gast": "gast"}


def _client(session_factory, key="k-mark", **kw):
    c = TestClient(create_app(session_factory=session_factory, api_keys=KEYS, **kw),
                   follow_redirects=False, base_url="https://testserver")
    c.post("/console/login", data={"key": key})
    return c


NO_BOX = object()


def _seed(session_factory, lists_hash=NO_BOX):
    """A document with stored text, and a box map made under ``lists_hash``
    (``None`` is a real value: no detection lists configured)."""
    with session_factory() as s:
        d = register(s, "besluit.pdf", filename="besluit.pdf")
        text = "Aan [PERSON:aabbccdd]."
        s.merge(DocumentText(document_id=d.id, anonymized_text=text))
        pseudonym_registry.register(s, d.id, text)
        if lists_hash is not NO_BOX:
            s.add(BoxMap(document_id=d.id, boxmap_hash="h", lists_hash=lists_hash,
                         boxes=[]))
        s.commit()
        return d.id


# --- console_pdf.state ------------------------------------------------------

def test_state_without_a_box_map_names_the_reason(session_factory):
    doc_id = _seed(session_factory)
    with session_factory() as s:
        st = console_pdf.state(s, doc_id, "lists-now")
    assert st["available"] is False and st["reason"] == console_pdf.NO_BOX_MAP
    assert "boxmap" in st["why"]


def test_state_with_a_current_box_map_is_available(session_factory):
    doc_id = _seed(session_factory, lists_hash="lists-now")
    with session_factory() as s:
        assert console_pdf.state(s, doc_id, "lists-now") == {"available": True}


def test_state_with_a_box_map_from_other_lists_is_stale(session_factory):
    doc_id = _seed(session_factory, lists_hash="lists-then")
    with session_factory() as s:
        st = console_pdf.state(s, doc_id, "lists-now")
    assert st["available"] is False and st["reason"] == console_pdf.STALE


# --- the document page ------------------------------------------------------

def test_the_page_links_the_redacted_pdf_when_there_is_a_box_map(session_factory):
    doc_id = _seed(session_factory, lists_hash=console_pdf.lists_hash())
    page = _client(session_factory).get(f"/console/documents/{doc_id}").text
    assert f'href="/documents/{doc_id}/redacted.pdf"' in page
    assert "Gelakte PDF" in page and "data-pdf-reason" not in page


def test_the_page_says_why_not_without_a_box_map(session_factory):
    doc_id = _seed(session_factory)
    page = _client(session_factory).get(f"/console/documents/{doc_id}").text
    assert "redacted.pdf" not in page
    assert 'data-pdf-reason="no-box-map"' in page and "Nog geen boxmap" in page


def test_the_page_says_why_not_with_a_stale_box_map(session_factory):
    doc_id = _seed(session_factory, lists_hash="lists-of-last-month")
    page = _client(session_factory).get(f"/console/documents/{doc_id}").text
    assert "redacted.pdf" not in page
    assert 'data-pdf-reason="stale"' in page and "verouderd" in page


def test_every_active_grant_offers_a_reveal_pdf(session_factory):
    """Offered for others' grants too: the screen offers, the door decides."""
    doc_id = _seed(session_factory)
    with session_factory() as s:
        for gid, who in (("g-mark", "mark"), ("g-hr", "hr")):
            s.add(GrantRecord(grant_id=gid, recipient=who, allowed_types=["PERSON"],
                              actor="mark", document_id=doc_id, status="active",
                              created_at=datetime.now(timezone.utc)))
        s.commit()
    c = _client(session_factory)
    page = c.get(f"/console/documents/{doc_id}").text
    assert 'data-reveal-pdf="g-mark"' in page and 'data-reveal-pdf="g-hr"' in page
    assert page.count("Onthul als PDF") == 2
    assert "/console/static/console_pdf.js" in page
    script = c.get("/console/static/console_pdf.js")
    assert script.status_code == 200 and "/reveal.pdf" in script.text


# --- the views themselves, through the API with the console cookie ----------

def _processed(session_factory, mem_store, mem_index, fake_embedder, pdf):
    kp = InMemoryKeyProvider()
    with session_factory() as s:
        doc = ingest(s, mem_store, pdf)
        s.commit()
        process(s, doc.id, mem_store,
                anonymizer=Pseudonymizer(kp, PostgresMappingStore(s)),
                search_index=mem_index, embedder=fake_embedder,
                key_provider=kp, mapping_store=PostgresMappingStore(s))
        s.commit()
    return kp, doc.id


def test_the_link_and_the_reveal_go_through_the_api_gates(
    session_factory, mem_store, mem_index, fake_embedder, born_digital_pii_pdf,
):
    kp, doc_id = _processed(session_factory, mem_store, mem_index, fake_embedder,
                            born_digital_pii_pdf)
    gs = InMemoryGrantStore()
    grant = gs.issue("mark", ["EMAIL"], actor="mark", document_id=doc_id)
    wiring = dict(store=mem_store, key_provider=kp, grant_store=gs)
    mark = _client(session_factory, "k-mark", **wiring)
    gast = _client(session_factory, "k-gast", **wiring)

    page = mark.get(f"/console/documents/{doc_id}").text
    assert f'href="/documents/{doc_id}/redacted.pdf"' in page
    r = mark.get(f"/documents/{doc_id}/redacted.pdf")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")

    body = {"grant_id": grant.grant_id, "types": ["EMAIL"]}
    r = mark.post(f"/documents/{doc_id}/reveal.pdf", json=body)
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    assert r.headers["content-type"] == "application/pdf"
    r = gast.post(f"/documents/{doc_id}/reveal.pdf", json=body)
    assert r.status_code == 403 and r.json()["detail"] == "grant not applicable"
