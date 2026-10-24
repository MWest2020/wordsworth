"""Manifest-driven ingest: the seam the reviewer requires -- these tests call
both ends (pilot-ingest-manifest). DB-integration; skips locally without a
database (see `tests/conftest.py`).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from sqlalchemy import select

from wordsworth.anonymizer import DeterministicAnonymizer
from wordsworth.ingest_manifest import ManifestResult, ingest_manifest_corpus
from wordsworth.manifest import ManifestEntry, read_manifest, write_entry
from wordsworth.models import AuditRecord, Document
from wordsworth.openanonymiser_driver import AnonymizationEngineError
from wordsworth.pipeline import current_state
from wordsworth.states import State

HERKOMST_SAMPLE = (
    Path(__file__).resolve().parents[1]
    / "docs" / "explanation" / "meting-woo-corpus-01.herkomst.jsonl"
)


def _entry(filename: str, pdf_bytes: bytes, *, url: str = "https://gooisemeren.nl/a.pdf",
          fetched_at: str = "2026-10-20T09:30:00+00:00") -> ManifestEntry:
    return ManifestEntry(
        file=filename, url=url, fetched_at=fetched_at,
        sha256=hashlib.sha256(pdf_bytes).hexdigest(), bytes=len(pdf_bytes),
        status="ok", ok=True,
    )


def _write_manifest(path: Path, *entries: ManifestEntry) -> None:
    with path.open("w") as fh:
        for entry in entries:
            write_entry(fh, entry)


def _report(tmp_path: Path, **overrides) -> Path:
    report = {
        "checked_by": "odin", "checked_at": "2026-10-23T18:00:00+00:00",
        "robots_txt": "User-agent: *\nAllow: /", "terms": "no terms page found",
        "anubis": "not present", "decision": "proceed",
        **overrides,
    }
    path = tmp_path / "check.json"
    path.write_text(json.dumps(report))
    return path


def _register_payload(session, document_id) -> dict:
    return session.execute(
        select(AuditRecord.payload)
        .where(AuditRecord.document_id == document_id, AuditRecord.step == "register")
    ).scalar_one()


def test_fetcher_written_record_round_trips(tmp_path, born_digital_pdf):
    """Test 2: a record written the way the fetcher writes it is read back
    identically by the manifest reader ingest uses."""
    entry = _entry("a.pdf", born_digital_pdf)
    manifest = tmp_path / "manifest.jsonl"
    _write_manifest(manifest, entry)
    assert read_manifest(manifest) == {"a.pdf": entry}


def test_herkomst_sample_uses_the_shared_vocabulary():
    """The committed sample (docs/explanation) was migrated off its old Dutch
    field names onto the shared manifest ones."""
    lines = [json.loads(line) for line in HERKOMST_SAMPLE.read_text().splitlines()
             if line.strip()]
    assert lines
    for row in lines:
        assert {"file", "url", "fetched_at"} <= row.keys()
        assert not {"bestand", "bron", "opgehaald"} & row.keys()


def test_provenance_reaches_the_audit_record(
    tmp_path, session_factory, mem_store, mem_index, fake_embedder, born_digital_pdf,
    monkeypatch,
):
    """Test 1: ingest with a manifest, then the `register` audit record
    carries the manifest's source_url and fetched_at."""
    monkeypatch.setenv("WORDSWORTH_BACKEND_ENV", "homelab")
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "a.pdf").write_bytes(born_digital_pdf)
    entry = _entry("a.pdf", born_digital_pdf)
    manifest = tmp_path / "manifest.jsonl"
    _write_manifest(manifest, entry)

    results = ingest_manifest_corpus(
        corpus, "zaak", manifest, _report(tmp_path),
        session_factory=session_factory, store=mem_store,
        anonymizer=DeterministicAnonymizer(), search_index=mem_index,
        embedder=fake_embedder,
    )
    assert results == [ManifestResult("a.pdf", True)]

    with session_factory() as session:
        doc = session.execute(
            select(Document).where(Document.filename == "a.pdf")).scalar_one()
        assert current_state(session, doc.id) == State.INDEXED
        payload = _register_payload(session, doc.id)
        assert payload["source_url"] == entry.url
        assert payload["fetched_at"] == "2026-10-20T09:30:00+00:00"


@pytest.mark.parametrize("dossier_b", ["zaak", "andere-zaak"])
def test_duplicate_delivery_fails_the_document(
    tmp_path, session_factory, mem_store, mem_index, fake_embedder, born_digital_pdf,
    dossier_b, monkeypatch,
):
    """Test 5: the same bytes delivered again (same or another dossier) keep
    their first provenance; the read-back fails the second delivery."""
    monkeypatch.setenv("WORDSWORTH_BACKEND_ENV", "homelab")
    first = tmp_path / "first"
    first.mkdir()
    (first / "a.pdf").write_bytes(born_digital_pdf)
    entry_a = _entry("a.pdf", born_digital_pdf, url="https://gooisemeren.nl/a.pdf")
    manifest_a = tmp_path / "manifest-a.jsonl"
    _write_manifest(manifest_a, entry_a)

    kwargs = dict(session_factory=session_factory, store=mem_store,
                  anonymizer=DeterministicAnonymizer(), search_index=mem_index,
                  embedder=fake_embedder)
    first_results = ingest_manifest_corpus(
        first, "zaak", manifest_a, _report(tmp_path), **kwargs)
    assert first_results == [ManifestResult("a.pdf", True)]

    second = tmp_path / "second"
    second.mkdir()
    (second / "b.pdf").write_bytes(born_digital_pdf)  # same bytes, other name
    entry_b = _entry("b.pdf", born_digital_pdf, url="https://gooisemeren.nl/b.pdf",
                     fetched_at="2026-10-21T10:00:00+00:00")
    manifest_b = tmp_path / "manifest-b.jsonl"
    _write_manifest(manifest_b, entry_b)

    second_results = ingest_manifest_corpus(
        second, dossier_b, manifest_b, _report(tmp_path), **kwargs)
    assert len(second_results) == 1
    assert second_results[0].ok is False
    assert "source_url" in second_results[0].reason


def test_openanonymiser_down_fails_the_run(
    tmp_path, session_factory, mem_store, mem_index, fake_embedder, born_digital_pdf,
    monkeypatch,
):
    """Test 7: the run fails (nothing ok, nothing indexed), and the document
    stays REGISTERED -- `anonymize` never committed `extracted` (the CI
    finding on PR #217): a failed anonymize leaves the last transition
    flushed but uncommitted, rolled back when the per-document session closes
    on the exception."""
    monkeypatch.setenv("WORDSWORTH_BACKEND_ENV", "homelab")
    monkeypatch.setenv("WORDSWORTH_RETRY_BASE_DELAY", "0")
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "a.pdf").write_bytes(born_digital_pdf)
    entry = _entry("a.pdf", born_digital_pdf)
    manifest = tmp_path / "manifest.jsonl"
    _write_manifest(manifest, entry)

    class _Down:
        def anonymize(self, text: str):
            raise AnonymizationEngineError("OpenAnonymiser unreachable")

    results = ingest_manifest_corpus(
        corpus, "zaak", manifest, _report(tmp_path),
        session_factory=session_factory, store=mem_store, anonymizer=_Down(),
        search_index=mem_index, embedder=fake_embedder,
    )
    assert len(results) == 1
    assert results[0].ok is False
    assert results[0].reason == "AnonymizationEngineError"
    assert mem_index._docs == {}

    with session_factory() as session:
        doc = session.execute(
            select(Document).where(Document.filename == "a.pdf")).scalar_one()
        assert current_state(session, doc.id) == State.REGISTERED
