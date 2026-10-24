"""Corpus-ingestion CLI guards, and the manifest-driven path (pilot-ingest-manifest)."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy import select

import wordsworth.ingest_manifest as ingest_manifest
from wordsworth import dossiers
from wordsworth.anonymizer import DeterministicAnonymizer
from wordsworth.ingest_corpus import main
from wordsworth.ingest_manifest import write_manifest_record
from wordsworth.models import AuditRecord, Document
from wordsworth.openanonymiser_driver import AnonymizationEngineError
from wordsworth.pipeline import current_state, ingest as pipeline_ingest
from wordsworth.states import State


def test_missing_corpus_dir_exits_nonzero_without_backends(tmp_path):
    missing = tmp_path / "does-not-exist"
    # Returns before wiring S3/OpenAnonymiser/OpenSearch/Ollama — no creds needed.
    assert main(["--corpus-dir", str(missing), "--dossier", "zaak"]) == 2


# --- pilot-ingest-manifest: tests 1-8 of design.md --------------------------

def _corpus(tmp_path, pdfs: dict[str, bytes]) -> Path:
    d = tmp_path / "corpus"
    d.mkdir()
    for name, data in pdfs.items():
        (d / name).write_bytes(data)
    return d


def _entry(name: str, data: bytes, url: str = "https://gooisemeren.nl/pub/a.pdf",
          fetched_at: datetime | None = None) -> dict:
    fetched_at = fetched_at or datetime(2026, 10, 20, 9, 30, tzinfo=timezone.utc)
    return {"file": name, "url": url, "fetched_at": fetched_at.isoformat(),
           "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
           "status": "fetched", "ok": True}


def _manifest(tmp_path, entries: list[dict], name: str = "manifest.jsonl") -> Path:
    p = tmp_path / name
    p.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
    return p


def _pilot_report(tmp_path, **overrides) -> Path:
    report = {"who": "mark", "when": "2026-10-24T09:00:00+00:00",
             "robots_txt": "User-agent: *\nAllow: /", "terms": "no terms page found",
             "anubis_status": "not present", "decision": "proceed"}
    report.update(overrides)
    p = tmp_path / "pilot-report.json"
    p.write_text(json.dumps(report))
    return p


@pytest.fixture
def homelab(monkeypatch):
    monkeypatch.setenv("WORDSWORTH_BACKEND_ENV", "homelab")


@pytest.fixture
def manifest_backends(monkeypatch, database_url, session_factory, mem_store,
                      mem_index, fake_embedder):
    """Real Postgres (session_factory's schema), fakes for everything else --
    the manifest path's own `.from_config()`/`OpenAnonymiserAnonymizer()` calls
    are monkeypatched so a test never reaches real S3/OpenSearch/Ollama/
    OpenAnonymiser. Returns the shared in-memory store."""
    monkeypatch.setenv("WORDSWORTH_DATABASE_URL", database_url)
    monkeypatch.setattr(ingest_manifest, "S3ObjectStore",
                        SimpleNamespace(from_config=lambda: mem_store))
    monkeypatch.setattr(ingest_manifest, "OpenSearchIndex",
                        SimpleNamespace(from_config=lambda: mem_index))
    monkeypatch.setattr(ingest_manifest, "OllamaEmbedder",
                        SimpleNamespace(from_config=lambda: fake_embedder))
    monkeypatch.setattr(ingest_manifest, "OpenAnonymiserAnonymizer",
                        lambda: DeterministicAnonymizer())
    return mem_store


def test_manifest_ingest_writes_provenance_to_the_audit_record(
        tmp_path, homelab, manifest_backends, session_factory, born_digital_pdf):
    """design.md test 1: provenance reaches the register audit record, and the
    manifest's fetched_at is recorded -- never the ingest time."""
    corpus = _corpus(tmp_path, {"a.pdf": born_digital_pdf})
    entry = _entry("a.pdf", born_digital_pdf)
    manifest = _manifest(tmp_path, [entry])
    report = _pilot_report(tmp_path)

    rc = main(["--corpus-dir", str(corpus), "--dossier", "pilot",
              "--manifest", str(manifest), "--pilot-report", str(report)])
    assert rc == 0

    with session_factory() as s:
        doc = s.execute(select(Document)).scalars().one()
        record = s.execute(
            select(AuditRecord).where(AuditRecord.document_id == doc.id,
                                      AuditRecord.step == "register")
        ).scalar_one()
    assert record.payload["source_url"] == entry["url"]
    assert record.payload["fetched_at"] == entry["fetched_at"]


def test_fetcher_written_record_is_ingested(
        tmp_path, homelab, manifest_backends, session_factory, born_digital_pdf):
    """design.md test 2: a record written the way the fetcher writes it is
    ingested; the docs sample it mirrors already uses the manifest's keys."""
    sample = Path("docs/explanation/meting-woo-corpus-01.herkomst.jsonl")
    first = json.loads(sample.read_text().splitlines()[0])
    assert {"file", "url", "fetched_at"} <= first.keys()
    assert not ({"bestand", "bron", "opgehaald"} & first.keys())

    corpus = _corpus(tmp_path, {"b.pdf": born_digital_pdf})
    manifest_path = tmp_path / "manifest.jsonl"
    with manifest_path.open("a") as fp:
        write_manifest_record(
            fp, file="b.pdf", url=first["url"],
            fetched_at=datetime(2026, 10, 20, 9, 30, tzinfo=timezone.utc),
            sha256=hashlib.sha256(born_digital_pdf).hexdigest(),
            bytes_=len(born_digital_pdf), status="fetched", ok=True)
    report = _pilot_report(tmp_path)

    rc = main(["--corpus-dir", str(corpus), "--dossier", "pilot",
              "--manifest", str(manifest_path), "--pilot-report", str(report)])
    assert rc == 0


def test_unlisted_file_aborts_the_run(tmp_path, homelab, born_digital_pdf, corrupt_pdf):
    """design.md test 3: an unlisted *.pdf aborts the run; nothing is ingested."""
    corpus = _corpus(tmp_path, {"a.pdf": born_digital_pdf, "b.pdf": corrupt_pdf})
    manifest = _manifest(tmp_path, [_entry("a.pdf", born_digital_pdf)])  # b.pdf missing
    report = _pilot_report(tmp_path)

    rc = main(["--corpus-dir", str(corpus), "--dossier", "pilot",
              "--manifest", str(manifest), "--pilot-report", str(report)])
    assert rc == 2


def test_sha256_mismatch_fails_loudly(tmp_path, homelab, born_digital_pdf):
    """design.md test 4."""
    corpus = _corpus(tmp_path, {"a.pdf": born_digital_pdf})
    entry = _entry("a.pdf", born_digital_pdf)
    entry["sha256"] = "0" * 64  # does not match the file's real digest
    manifest = _manifest(tmp_path, [entry])
    report = _pilot_report(tmp_path)

    rc = main(["--corpus-dir", str(corpus), "--dossier", "pilot",
              "--manifest", str(manifest), "--pilot-report", str(report)])
    assert rc == 2


def test_duplicate_key_fails_the_read_back(
        tmp_path, homelab, manifest_backends, session_factory, born_digital_pdf):
    """design.md test 5: these bytes are already a live document, in another
    dossier, with no provenance -- the read-back fails this document and the
    run exits non-zero, but ingest() still adds the new dossier membership
    (unchanged: the key still ignores the dossier)."""
    with session_factory() as s:
        existing = pipeline_ingest(s, manifest_backends, born_digital_pdf,
                                   dossier="gooise-meren-woo-2022")
        s.commit()
        existing_id = existing.id

    corpus = _corpus(tmp_path, {"a.pdf": born_digital_pdf})
    manifest = _manifest(tmp_path, [_entry("a.pdf", born_digital_pdf)])
    report = _pilot_report(tmp_path)

    rc = main(["--corpus-dir", str(corpus), "--dossier", "pilot",
              "--manifest", str(manifest), "--pilot-report", str(report)])
    assert rc == 1

    with session_factory() as s:
        for name in ("gooise-meren-woo-2022", "pilot"):
            d = next(x for x in dossiers.listing(s) if x["name"] == name)
            assert existing_id in dossiers.documents_in(s, [UUID(d["id"])])


def test_missing_or_alma_backend_is_refused(tmp_path, monkeypatch, born_digital_pdf):
    """design.md test 6."""
    corpus = _corpus(tmp_path, {"a.pdf": born_digital_pdf})
    manifest = _manifest(tmp_path, [_entry("a.pdf", born_digital_pdf)])
    report = _pilot_report(tmp_path)
    args = ["--corpus-dir", str(corpus), "--dossier", "pilot",
           "--manifest", str(manifest), "--pilot-report", str(report)]

    monkeypatch.delenv("WORDSWORTH_BACKEND_ENV", raising=False)
    assert main(args) == 2

    monkeypatch.setenv("WORDSWORTH_BACKEND_ENV", "")
    assert main(args) == 2

    monkeypatch.setenv("WORDSWORTH_BACKEND_ENV", "alma")
    assert main(args) == 2


def test_openanonymiser_down_fails_the_run(
        tmp_path, homelab, manifest_backends, session_factory, monkeypatch,
        born_digital_pdf):
    """design.md test 7: a layer that did not run fails the run; nothing is indexed."""
    monkeypatch.setenv("WORDSWORTH_RETRY_ATTEMPTS", "1")  # no slow backoff in a test

    def _always_down(text):
        raise AnonymizationEngineError("OpenAnonymiser unreachable")

    monkeypatch.setattr(ingest_manifest, "OpenAnonymiserAnonymizer",
                        lambda: SimpleNamespace(anonymize=_always_down))

    corpus = _corpus(tmp_path, {"a.pdf": born_digital_pdf})
    manifest = _manifest(tmp_path, [_entry("a.pdf", born_digital_pdf)])
    report = _pilot_report(tmp_path)

    rc = main(["--corpus-dir", str(corpus), "--dossier", "pilot",
              "--manifest", str(manifest), "--pilot-report", str(report)])
    assert rc == 1

    with session_factory() as s:
        doc = s.execute(select(Document)).scalars().one()
        # Stuck at `extracted`: anonymize raised past retry, never indexed.
        assert current_state(s, doc.id) == State.EXTRACTED


def test_pilot_report_gate(tmp_path, homelab, born_digital_pdf):
    """design.md test 8: no completed check, and decision != proceed, both refuse."""
    corpus = _corpus(tmp_path, {"a.pdf": born_digital_pdf})
    manifest = _manifest(tmp_path, [_entry("a.pdf", born_digital_pdf)])
    args = ["--corpus-dir", str(corpus), "--dossier", "pilot",
           "--manifest", str(manifest)]

    incomplete = tmp_path / "incomplete.json"
    incomplete.write_text(json.dumps({"who": "mark", "decision": "proceed"}))
    assert main(args + ["--pilot-report", str(incomplete)]) == 2

    stopped = _pilot_report(tmp_path, decision="stop")
    assert main(args + ["--pilot-report", str(stopped)]) == 2
