# SPDX-License-Identifier: MIT
"""`POST /ingest` requires corpus read (ingest-requires-corpus-read, #526).

A caller on no list, and an issuer who is no reader, get 403 before FastAPI
reads the upload: `starlette.requests.Request.form` is counted, and a refused
upload never calls it. A reader still ingests; a missing key is still 401;
with authentication off nothing changes. The DB-backed half shows a refused
upload writes no row and no object, and a reader's upload is indexed.
"""
from __future__ import annotations

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from starlette.requests import Request

from inventory_app import declared_only_ingest_app, full_app, ungated_ingest_app
from wordsworth import read_gate
from wordsworth.anonymizer import DeterministicAnonymizer
from wordsworth.api import create_app
from wordsworth.models import AuditRecord, Document
from wordsworth.search_index import InMemoryIndex

REFUSED = {"detail": "caller not authorized for corpus read"}
PDF = {"files": ("a.pdf", b"%PDF-1.4 not really", "application/pdf")}


@pytest.fixture
def forms_read(monkeypatch) -> list:
    """One entry per `Request.form()` call: FastAPI reads a multipart body
    through it, so an empty list means the upload was never parsed."""
    calls: list = []
    original = Request.form

    def counting(self, *a, **kw):
        calls.append(self.url.path)
        return original(self, *a, **kw)

    monkeypatch.setattr(Request, "form", counting)
    return calls


def _post(app, key: str | None, **kw):
    client = TestClient(app, raise_server_exceptions=False)
    headers = {"X-API-Key": key} if key else {}
    return client.post("/ingest", files=PDF, params={"dossier": "zaak"},
                       headers=headers, **kw)


@pytest.mark.parametrize("key", ["kderde", "kuitgever"], ids=["no list", "issuer"])
def test_a_caller_without_corpus_read_is_refused_before_the_upload_is_read(
        forms_read, key):
    resp = _post(full_app(), key)
    assert (resp.status_code, resp.json()) == (403, REFUSED)
    assert forms_read == []


def test_a_missing_key_is_still_401_and_reads_nothing(forms_read):
    resp = _post(full_app(), None)
    assert resp.status_code == 401
    assert forms_read == []


def test_a_reader_gets_past_the_gate_and_the_upload_is_read(forms_read):
    """The instrument works: the same request as a reader reaches the route
    (the stand-in store fails it later), and the form is read."""
    resp = _post(full_app(), "klezer")
    assert resp.status_code not in (401, 403)
    assert forms_read == ["/ingest"]


def test_with_authentication_off_ingest_is_open_as_before(forms_read):
    app = full_app(api_keys={}, corpus_read_labels=[])
    resp = TestClient(app, raise_server_exceptions=False).post("/ingest", files=PDF)
    assert resp.status_code == 400 and "dossier" in resp.json()["detail"]


def test_without_gate_first_the_upload_is_read_before_the_403(forms_read):
    """Why `GateFirst`: a declared gate alone refuses, but only after FastAPI
    has parsed the multipart body."""
    resp = _post(declared_only_ingest_app(), "kderde")
    assert resp.status_code == 403
    assert forms_read == ["/ingest"]


def test_without_any_gate_a_caller_on_no_list_reaches_the_route(forms_read):
    """#526 as found: past authentication, into validation."""
    resp = _post(ungated_ingest_app(), "kderde")
    assert resp.status_code not in (401, 403)


def test_gate_first_needs_a_declared_gate():
    router = APIRouter()
    with pytest.raises(TypeError, match="without a declared gate"):
        router.add_api_route("/x", lambda: {}, methods=["POST"],
                             route_class_override=read_gate.GateFirst)
    router.add_api_route("/y", lambda: {}, methods=["POST"],
                         route_class_override=read_gate.GateFirst,
                         dependencies=[Depends(read_gate.corpus_read(["a"]))])


# --- DB-backed: nothing written on a refusal; a reader ingests ---------------

KEYS = {"klezer": "lezer", "kderde": "derde"}


def _db_app(session_factory, store, embedder):
    return TestClient(create_app(
        session_factory=session_factory, store=store, search_index=InMemoryIndex(),
        embedder=embedder, anonymizer=DeterministicAnonymizer(), api_keys=KEYS,
        corpus_read_labels=["lezer"], rate_limiters={}),
        raise_server_exceptions=False)


def _rows(session_factory) -> tuple[int, int]:
    with session_factory() as s:
        return (s.execute(select(func.count()).select_from(Document)).scalar_one(),
                s.execute(select(func.count()).select_from(AuditRecord)).scalar_one())


def test_a_refused_upload_writes_nothing_and_a_reader_ingests(
        session_factory, mem_store, fake_embedder, born_digital_pii_pdf):
    client = _db_app(session_factory, mem_store, fake_embedder)
    files = {"files": ("a.pdf", born_digital_pii_pdf, "application/pdf")}
    refused = client.post("/ingest", params={"dossier": "zaak-a"}, files=files,
                          headers={"X-API-Key": "kderde"})
    assert (refused.status_code, refused.json()) == (403, REFUSED)
    assert _rows(session_factory) == (0, 0)
    assert mem_store._data == {}

    files = {"files": ("a.pdf", born_digital_pii_pdf, "application/pdf")}
    ok = client.post("/ingest", params={"dossier": "zaak-a"}, files=files,
                     headers={"X-API-Key": "klezer"})
    assert ok.status_code == 200, ok.text
    assert ok.json()["results"][0]["state"] == "indexed"
    assert _rows(session_factory)[0] == 1 and mem_store._data
