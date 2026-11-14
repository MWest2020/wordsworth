# SPDX-License-Identifier: MIT
"""The PDF views where they must NOT be offered (console-pdf-views): no object
store, an unknown document, a caller without corpus read. And the behaviour of
static/console_pdf.js, tested as the real file in node.

DB-backed: runs against a real Postgres and skips locally without one."""
from __future__ import annotations

import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from wordsworth import console_pdf, pseudonym_registry
from wordsworth.api import create_app
from wordsworth.models import DocumentText, GrantRecord
from wordsworth.pipeline import register

KEYS = {"k-mark": "mark", "k-gast": "gast"}


def _client(session_factory, key="k-mark", **kw):
    c = TestClient(create_app(session_factory=session_factory, api_keys=KEYS, **kw),
                   follow_redirects=False, base_url="https://testserver")
    c.post("/console/login", data={"key": key})
    return c


def _seed_with_grant(session_factory):
    with session_factory() as s:
        d = register(s, "besluit.pdf", filename="besluit.pdf")
        text = "Aan [PERSON:aabbccdd]."
        s.merge(DocumentText(document_id=d.id, anonymized_text=text))
        pseudonym_registry.register(s, d.id, text)
        s.add(GrantRecord(grant_id="g-mark", recipient="mark", allowed_types=["PERSON"],
                          actor="mark", document_id=d.id, status="active",
                          created_at=datetime.now(timezone.utc)))
        s.commit()
        return d.id


def test_without_an_object_store_there_are_no_pdf_views(session_factory):
    """The PDF routes are only mounted with a store (`serve` can run without
    one): no link, no button, and the page says so."""
    doc_id = _seed_with_grant(session_factory)
    c = _client(session_factory)                       # no store
    assert c.post(f"/documents/{doc_id}/reveal.pdf",
                  json={"grant_id": "g-mark"}).status_code in (404, 405)
    page = c.get(f"/console/documents/{doc_id}").text
    assert 'data-pdf-reason="no-store"' in page and "niet beschikbaar" in page
    assert "redacted.pdf" not in page
    assert "data-reveal-pdf" not in page and "Onthul als PDF" not in page
    assert 'data-reveal="g-mark"' in page              # the text reveal stays


def test_state_without_a_store_says_so(session_factory):
    doc_id = _seed_with_grant(session_factory)
    with session_factory() as s:
        st = console_pdf.state(s, doc_id, None, pdf_views=False)
    assert st["available"] is False and st["reason"] == console_pdf.NO_STORE


def test_an_unknown_document_gets_no_pdf_block(session_factory, mem_store):
    unknown = uuid.uuid4()
    with session_factory() as s:
        assert console_pdf.state(s, unknown, None) is None
    page = _client(session_factory, store=mem_store).get(
        f"/console/documents/{unknown}").text
    assert 'id="pdf"' not in page and "data-pdf-reason" not in page


def test_without_corpus_read_neither_link_nor_reason_is_shown(session_factory,
                                                              mem_store):
    """`gast` is logged in but may not read the corpus: the page is refused
    whole, so nothing about the PDF (not even why it is missing) leaks."""
    doc_id = _seed_with_grant(session_factory)
    gast = _client(session_factory, "k-gast", store=mem_store,
                   corpus_read_labels=["mark"])
    r = gast.get(f"/console/documents/{doc_id}", headers={"Accept": "text/html"})
    assert r.status_code == 403
    assert "redacted.pdf" not in r.text and "boxmap" not in r.text
    assert "Onthul als PDF" not in r.text
    r = gast.get(f"/documents/{doc_id}/redacted.pdf")
    assert r.status_code == 403


def test_the_javascript_behaves(tmp_path):
    """What console_pdf.js posts, shows and revokes, in node on the real file."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available")
    suite = Path(__file__).with_name("test_console_pdf.js")
    r = subprocess.run([node, str(suite)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "alle gevallen goed" in r.stdout
