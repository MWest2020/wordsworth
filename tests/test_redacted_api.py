"""GET /documents/{id}/redacted.pdf (pdf-redaction). DB-backed: runs against a
real Postgres and skips locally without one, like the other DB integration
tests."""
from __future__ import annotations

import io
import json
from uuid import uuid4

import pypdf
from fastapi.testclient import TestClient

from wordsworth.api import create_app
from wordsworth.detection_lists import DetectionLists
from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.pipeline import ingest, process, reanonymize
from wordsworth.pseudonymizer import Pseudonymizer, ReversibleAnonymizer

PII_BSN = "123456782"


def _write_lists(tmp_path, deny_rule_count: int) -> str:
    (tmp_path / "allow.json").write_text("{}")
    deny = ({"KENTEKEN": [f"NOOIT-{i}" for i in range(deny_rule_count)]}
            if deny_rule_count else {})
    (tmp_path / "deny.json").write_text(json.dumps(deny))
    return str(tmp_path)


def _client(session_factory, mem_store, kp):
    return TestClient(create_app(session_factory=session_factory, store=mem_store,
                                 key_provider=kp))


def _ingest_and_process(session_factory, mem_store, mem_index, fake_embedder, pdf,
                        kp, anonymizer_factory=None):
    with session_factory() as s:
        doc = ingest(s, mem_store, pdf)
        s.commit()
        anon = (anonymizer_factory(s) if anonymizer_factory
                else Pseudonymizer(kp, PostgresMappingStore(s)))
        process(s, doc.id, mem_store, anonymizer=anon,
                search_index=mem_index, embedder=fake_embedder,
                key_provider=kp, mapping_store=PostgresMappingStore(s))
        s.commit()
        return doc.id


def test_redacted_pdf_served_and_cached(session_factory, mem_store, mem_index,
                                        fake_embedder, born_digital_pii_pdf):
    kp = InMemoryKeyProvider()
    doc_id = _ingest_and_process(session_factory, mem_store, mem_index,
                                 fake_embedder, born_digital_pii_pdf, kp)
    client = _client(session_factory, mem_store, kp)

    r = client.get(f"/documents/{doc_id}/redacted.pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    text = pypdf.PdfReader(io.BytesIO(r.content)).pages[0].extract_text()
    assert PII_BSN not in text

    calls: list[str] = []
    original_put = mem_store.put
    mem_store.put = lambda key, data: (calls.append(key), original_put(key, data))[1]
    try:
        r2 = client.get(f"/documents/{doc_id}/redacted.pdf")
    finally:
        mem_store.put = original_put
    assert r2.status_code == 200
    assert r2.content == r.content
    assert calls == []  # the second call read the cached object, not a re-render


def test_unknown_document_is_404(session_factory, mem_store):
    client = _client(session_factory, mem_store, InMemoryKeyProvider())
    assert client.get(f"/documents/{uuid4()}/redacted.pdf").status_code == 404


def test_no_box_map_yet_is_409(session_factory, mem_store, mem_index, fake_embedder,
                               born_digital_pii_pdf):
    kp = InMemoryKeyProvider()
    with session_factory() as s:
        doc = ingest(s, mem_store, born_digital_pii_pdf)
        s.commit()
        # No key_provider/mapping_store passed -> irreversible-equivalent path,
        # no box map is ever computed.
        process(s, doc.id, mem_store,
                anonymizer=Pseudonymizer(kp, PostgresMappingStore(s)),
                search_index=mem_index, embedder=fake_embedder)
        s.commit()
        doc_id = doc.id
    client = _client(session_factory, mem_store, kp)
    assert client.get(f"/documents/{doc_id}/redacted.pdf").status_code == 409


def test_stale_lists_then_reanonymize(session_factory, mem_store, mem_index,
                                      fake_embedder, born_digital_pii_pdf,
                                      tmp_path, monkeypatch):
    lists_dir = _write_lists(tmp_path, deny_rule_count=0)
    monkeypatch.setenv("WORDSWORTH_DETECTION_LISTS", lists_dir)

    kp = InMemoryKeyProvider()
    with session_factory() as s:
        doc = ingest(s, mem_store, born_digital_pii_pdf)
        s.commit()
        process(s, doc.id, mem_store,
                anonymizer=ReversibleAnonymizer(
                    kp, PostgresMappingStore(s), detect=lambda t: [],
                    lists=DetectionLists.load(lists_dir)),
                search_index=mem_index, embedder=fake_embedder,
                key_provider=kp, mapping_store=PostgresMappingStore(s))
        s.commit()
        doc_id = doc.id

    client = _client(session_factory, mem_store, kp)
    assert client.get(f"/documents/{doc_id}/redacted.pdf").status_code == 200

    # The lists change on disk (git deploy) -- same directory, new content, new hash.
    _write_lists(tmp_path, deny_rule_count=1)
    r = client.get(f"/documents/{doc_id}/redacted.pdf")
    assert r.status_code == 409
    assert r.json()["detail"] == "stale"

    with session_factory() as s:
        reanonymize(s, doc_id, mem_store,
                   anonymizer=ReversibleAnonymizer(
                       kp, PostgresMappingStore(s), detect=lambda t: [],
                       lists=DetectionLists.load(lists_dir)),
                   search_index=mem_index, embedder=fake_embedder,
                   key_provider=kp, mapping_store=PostgresMappingStore(s))
        s.commit()
    r2 = client.get(f"/documents/{doc_id}/redacted.pdf")
    assert r2.status_code == 200
    text = pypdf.PdfReader(io.BytesIO(r2.content)).pages[0].extract_text()
    assert PII_BSN not in text
