# SPDX-License-Identifier: MIT
"""`delete-removes-original-scan` task 5: every caller removes the scan --
the API, `wordsworth-delete` with a plain object store, and a dossier
deletion -- and `original_scan` reaches every report, dry run and real."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from shred_setup import key_row, originals
from scan_setup import recover_document

from wordsworth import dossiers
from wordsworth.api import create_app
from wordsworth.delete_cli import main
from wordsworth.dossier_deletion import delete_dossier
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.pipeline import ingest
from wordsworth.search_index import InMemoryIndex

ISSUER = {"api_keys": {"k-issuer": "issuer-caller"},
          "grant_issuer_labels": ["issuer-caller"]}
HEADERS = {"X-API-Key": "k-issuer"}


def test_the_api_removes_the_scan(session_factory, scanned_pdf):
    store = originals()
    with session_factory() as s:
        doc_id, scan_key, ocr_key = recover_document(s, store, scanned_pdf)
    client = TestClient(create_app(session_factory=session_factory, store=store,
                                   search_index=InMemoryIndex(), **ISSUER))

    r = client.delete(f"/documents/{doc_id}", headers=HEADERS)

    assert r.status_code == 200
    assert r.json()["original_scan"] == 1
    assert not store.objects.exists(scan_key)
    with session_factory() as s:
        assert key_row(s, scan_key) is None


def test_the_cli_with_a_plain_store_removes_the_scan(session_factory, capsys,
                                                      scanned_pdf):
    store = InMemoryObjectStore()  # what wordsworth-delete builds: no keys
    with session_factory() as s:
        doc_id, scan_key, ocr_key = recover_document(s, store, scanned_pdf)

    code = main([str(doc_id), "--actor", "operator"], session_factory=session_factory,
               store=store, index=InMemoryIndex(), issuer_labels=["operator"])

    assert code == 0
    report = json.loads(capsys.readouterr().out)["results"][0]
    assert report["original_scan"] == 1
    assert not store.exists(scan_key)


def test_a_dossier_deletion_removes_the_scan_of_an_exclusive_member(session_factory,
                                                                    scanned_pdf):
    store = originals()
    with session_factory() as s:
        dossier = dossiers.ensure(s, "zaak")
        doc_id, scan_key, ocr_key = recover_document(s, store, scanned_pdf)
        dossiers.add(s, dossier.id, doc_id, actor="t")
        s.commit()
        dossier_id = dossier.id

        report = delete_dossier(s, dossier_id, store, InMemoryIndex(), actor="t")
        s.commit()

    assert report.deleted == [str(doc_id)] and report.original_scan == 1
    assert not store.objects.exists(scan_key)


def test_a_dossier_report_sums_original_scan_and_a_shared_member_keeps_its_scan(
        session_factory, scanned_pdf):
    """A dossier with one exclusive recovered document and one shared with
    another dossier: the sum counts only the exclusive one's scan, dry run
    and real, and the shared member keeps its scan."""
    store = originals()
    with session_factory() as s:
        mine, theirs = dossiers.ensure(s, "zaak-a"), dossiers.ensure(s, "zaak-b")
        exclusive_id, exclusive_scan, _ = recover_document(s, store, scanned_pdf)
        shared_doc = ingest(s, store, b"%PDF-1.4 a plain second document")
        s.commit()
        dossiers.add(s, mine.id, exclusive_id, actor="t")
        dossiers.add(s, mine.id, shared_doc.id, actor="t")
        dossiers.add(s, theirs.id, shared_doc.id, actor="t")
        s.commit()
        mine_id, shared_id = mine.id, shared_doc.id

        dry = delete_dossier(s, mine_id, store, InMemoryIndex(), actor="t", dry_run=True)
        s.rollback()
    assert dry.original_scan == 1
    assert store.objects.exists(exclusive_scan)

    with session_factory() as s:
        real = delete_dossier(s, mine_id, store, InMemoryIndex(), actor="t")
        s.commit()

    assert real.deleted == [str(exclusive_id)] and real.released == [str(shared_id)]
    assert real.original_scan == 1
    assert not store.objects.exists(exclusive_scan)
