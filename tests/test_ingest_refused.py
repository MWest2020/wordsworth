# SPDX-License-Identifier: MIT
"""#452 review: an `IngestRaceError` is not a dead end. The API answers with
a fixed, readable `error` naming `wordsworth-release-deleted-keys`; the server
log carries the document id and the object key (a sha256), never the
filename; `wordsworth-ingest` reports the file and goes on."""
from __future__ import annotations

import hashlib
import json
import logging

from fastapi.testclient import TestClient

import wordsworth.ingest_corpus as ingest_corpus_mod
from race_setup import SpyOriginalsStore
from wordsworth.anonymizer import DeterministicAnonymizer
from wordsworth.api import create_app
from wordsworth.deletion import delete_document
from wordsworth.ingest_lock import IngestRaceError
from wordsworth.models import Document
from wordsworth.pipeline import ingest
from wordsworth.search_index import InMemoryIndex
from wordsworth.states import State

REFUSED = b"%PDF-1.4 deleted before deletions released the key"
KEY = "documents/" + hashlib.sha256(REFUSED).hexdigest()
FILENAME = "Jan Jansen bezwaar.pdf"  # a filename can be a name


def _deleted_still_holding_key(session_factory, store):
    with session_factory() as s:
        doc_id = ingest(s, store, REFUSED).id
        s.commit()
        delete_document(s, doc_id, store, InMemoryIndex(), actor="t")
        s.commit()
        s.get(Document, doc_id).object_key = KEY  # as before the release
        s.commit()
    store.put_for.clear()
    return doc_id


def _refusal_lines(caplog):
    return [json.loads(r.getMessage()) for r in caplog.records
            if '"ingest_refused"' in r.getMessage()]


def test_the_api_answers_a_readable_error_and_logs_ids_only(
        session_factory, mem_index, fake_embedder, caplog):
    store = SpyOriginalsStore()
    doc_id = _deleted_still_holding_key(session_factory, store)
    caplog.set_level(logging.ERROR, logger="wordsworth.pipeline")
    client = TestClient(create_app(
        session_factory=session_factory, store=store, search_index=mem_index,
        embedder=fake_embedder, anonymizer=DeterministicAnonymizer()))

    r = client.post("/ingest", params={"dossier": "zaak"},
                    files=[("files", (FILENAME, REFUSED, "application/pdf"))])

    assert r.status_code == 200
    result = r.json()["results"][0]
    assert result["state"] == "error"
    assert result["error"] == IngestRaceError.public
    assert "wordsworth-release-deleted-keys" in result["error"]
    assert store.put_for == []
    [line] = _refusal_lines(caplog)
    assert line["document_id"] == str(doc_id) and line["object_key"] == KEY
    assert FILENAME not in json.dumps(line)


def test_the_corpus_cli_reports_the_refusal_and_goes_on(
        tmp_path, monkeypatch, capsys, session_factory, mem_index, fake_embedder):
    from test_ingest_corpus import _wire_fake_backends

    store = SpyOriginalsStore()
    _deleted_still_holding_key(session_factory, store)
    (tmp_path / "a-refused.pdf").write_bytes(REFUSED)
    (tmp_path / "b-fine.pdf").write_bytes(b"%PDF-1.4 a file that is fine")
    _wire_fake_backends(monkeypatch, session_factory, store, mem_index, fake_embedder)
    monkeypatch.setattr(ingest_corpus_mod, "process", lambda *a, **kw: State.INDEXED)

    rc = ingest_corpus_mod.main(["--corpus-dir", str(tmp_path), "--dossier", "zaak"])

    assert rc == 1  # the fine file indexed, the refused one did not
    err = capsys.readouterr().err
    assert f"a-refused.pdf: refused: {IngestRaceError.public}" in err
    assert "Traceback" not in err
    assert len(store.put_for) == 1  # the next file was still ingested
