"""Anonymised-docs ZIP export over a real DB (add-export). CI runs this."""
from __future__ import annotations

import io
import zipfile

from fastapi.testclient import TestClient

from wordsworth import audit
from wordsworth.api import create_app
from wordsworth.models import DocumentText
from wordsworth.pipeline import register
from wordsworth.states import State


def _make_indexed(session, key: str, text: str):
    doc = register(session, key)  # -> REGISTERED
    audit.append(session, document_id=doc.id,
                 from_state=State.REGISTERED.value, to_state=State.INDEXED.value,
                 step="index")
    session.merge(DocumentText(document_id=doc.id, anonymized_text=text))
    session.flush()
    return doc


def test_export_zip_has_one_entry_per_indexed_doc_deidentified(session_factory, session):
    d1 = _make_indexed(session, "k1", "besluit [BSN:aaaa1111] over parkeren")
    d2 = _make_indexed(session, "k2", "[PERSON:bbbb2222] in de straat")
    session.commit()

    client = TestClient(create_app(session_factory=session_factory, rate_limiters={}))
    r = client.get("/export/anonymized.zip")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    assert set(zf.namelist()) == {f"{d1.id}.txt", f"{d2.id}.txt"}
    assert zf.read(f"{d1.id}.txt").decode() == "besluit [BSN:aaaa1111] over parkeren"
    assert "123456782" not in zf.read(f"{d1.id}.txt").decode()  # no clear PII


def test_export_zip_filters_by_document_ids(session_factory, session):
    d1 = _make_indexed(session, "k1", "een [BSN:aaaa1111]")
    _make_indexed(session, "k2", "twee [PERSON:bbbb2222]")
    session.commit()

    client = TestClient(create_app(session_factory=session_factory, rate_limiters={}))
    r = client.get("/export/anonymized.zip", params={"document_ids": str(d1.id)})
    assert r.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    assert zf.namelist() == [f"{d1.id}.txt"]


def test_export_zip_skips_non_indexed(session_factory, session):
    _make_indexed(session, "k1", "indexed [BSN:aaaa1111]")
    register(session, "k2")  # stays REGISTERED, no anonymized text
    session.commit()

    client = TestClient(create_app(session_factory=session_factory, rate_limiters={}))
    r = client.get("/export/anonymized.zip")
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    assert len(zf.namelist()) == 1  # only the INDEXED document
