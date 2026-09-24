# SPDX-License-Identifier: MIT
"""One live document per stored object, enforced (one-document-per-object, release 2).

Release 1 retired the 173 copies that the August ingest runs left. These tests
pin what stops the next one: the database refuses a second live document for
the same bytes, a registration that loses that race gets the winner, and an OCR
recovery that lands on an object already held retires itself.
"""
import hashlib
import threading
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, insert, select, text
from sqlalchemy.exc import IntegrityError

from wordsworth import dossiers, recovery
from wordsworth.anonymizer import DeterministicAnonymizer
from wordsworth.api import create_app
from wordsworth.db import init_schema, make_engine
from wordsworth.models import AuditRecord, Document
from wordsworth.ocr import FixedOcrEngine
from wordsworth.pipeline import current_state, ingest, process, register, register_live
from wordsworth.search_index import InMemoryIndex
from wordsworth.states import State

KEY = "documents/" + "ef" * 32
#: One fixed OCR output. FixedOcrEngine is not byte-deterministic, so two scans
#: only OCR to the same object if the engine hands back the very same bytes.
OCR_PDF = FixedOcrEngine("Herstelde tekst uit een scan. " * 20).ocr(b"%PDF-1.4")
OCR_KEY = "documents/" + hashlib.sha256(OCR_PDF).hexdigest()


class _SameOcr:
    lang = "nld"

    def ocr(self, pdf_bytes: bytes) -> bytes:
        return OCR_PDF


def test_the_database_refuses_a_second_live_document_for_the_same_bytes(session):
    register(session, KEY)
    session.flush()
    with pytest.raises(IntegrityError, match="uq_documents_live_object_key"):
        register(session, KEY)
        session.flush()
    session.rollback()


def test_a_superseded_copy_does_not_count(session):
    live = register(session, KEY)
    session.flush()
    session.execute(insert(Document).values(object_key=KEY, superseded_by=live.id))
    session.commit()
    assert session.scalar(select(func.count()).select_from(Document)
                          .where(Document.object_key == KEY)) == 2


def test_the_same_bytes_registered_twice_give_one_document(session):
    first = register_live(session, KEY)
    session.commit()
    assert register_live(session, KEY).id == first.id


def test_two_registrations_at_once_give_one_document(session_factory):
    """The race that made the copies: both find nothing, both insert. The index
    lets one through; the other waits, is refused, and adopts the winner."""
    results, errors = [], []
    first = session_factory()
    results.append(register_live(first, KEY).id)          # inserted, not committed

    def second():
        try:
            with session_factory() as s:
                results.append(register_live(s, KEY).id)  # waits on the index
                s.commit()
        except Exception as exc:   # noqa: BLE001 -- the failure is the finding
            errors.append(exc)

    t = threading.Thread(target=second)
    t.start()
    time.sleep(0.5)
    first.commit()
    first.close()
    t.join(10)
    assert errors == []
    assert results[0] == results[1]
    with session_factory() as s:
        assert s.scalar(select(func.count()).select_from(Document)
                        .where(Document.object_key == KEY)) == 1


def _parked_scan(session, store, scanned_pdf, dossier):
    doc = ingest(session, store, scanned_pdf, dossier=dossier)
    assert process(session, doc.id, store) == State.UNPROCESSABLE_OCR
    session.commit()
    return doc


def test_an_ocr_landing_on_a_held_object_retires_itself(session, mem_store,
                                                        scanned_pdf):
    owner = register(session, OCR_KEY)
    session.commit()
    scan = _parked_scan(session, mem_store, scanned_pdf, dossier="Z")
    scan_key = scan.object_key

    assert recovery.recover(session, scan.id, mem_store, threshold=10,
                            engine=_SameOcr()) == State.SUPERSEDED
    session.commit()

    assert current_state(session, scan.id) == State.SUPERSEDED
    retired = session.get(Document, scan.id)
    assert retired.superseded_by == owner.id
    assert retired.object_key == scan_key          # the scan is still what it is
    record = session.execute(select(AuditRecord).where(
        AuditRecord.document_id == scan.id, AuditRecord.step == "supersede")).scalar_one()
    assert record.payload["as_object"] == OCR_KEY
    z = next(d for d in dossiers.listing(session) if d["name"] == "Z")
    assert str(owner.id) in {str(i) for i in dossiers.documents_in(session, [z["id"]])}


def test_the_api_hands_a_retired_scans_dossier_to_the_index(session_factory, mem_store,
                                                            scanned_pdf, fake_embedder,
                                                            monkeypatch):
    """The ingest endpoint must not process a retired document, and must tell
    the index that the owner gained the dossier."""
    with session_factory() as s:
        owner_id = register(s, OCR_KEY).id
        s.commit()
    index = InMemoryIndex()
    index.index(str(owner_id), "tekst", OCR_KEY)
    monkeypatch.setattr(recovery, "_default_ocr_engine", lambda: _SameOcr())
    c = TestClient(create_app(session_factory=session_factory, store=mem_store,
                              search_index=index, embedder=fake_embedder,
                              anonymizer=DeterministicAnonymizer()))
    r = c.post("/ingest", params={"dossier": "Z"},
               files={"files": ("scan.pdf", scanned_pdf, "application/pdf")})
    assert r.status_code == 200, r.text
    with session_factory() as s:
        z = next(d for d in dossiers.listing(s) if d["name"] == "Z")
    assert str(z["id"]) in index._dossiers[str(owner_id)]


def test_init_adds_the_constraint_to_a_database_without_it(legacy_copies, database_url):
    engine = make_engine(database_url)
    init_schema(engine, attempts=1)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT to_regclass('uq_documents_live_object_key')")).scalar()


def test_init_refuses_loudly_while_copies_remain(legacy_copies, database_url):
    """Creating the constraint over copies must fail, not be skipped: an init
    that quietly left it out would leave the rule unenforced unannounced."""
    with legacy_copies() as s:
        register(s, KEY)
        register(s, KEY)
        s.commit()
    with pytest.raises(IntegrityError):
        init_schema(make_engine(database_url), attempts=1)
