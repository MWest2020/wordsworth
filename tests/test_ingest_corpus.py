"""Corpus-ingestion CLI guards — offline (no backends contacted) — and the
manifest-driven path (pilot-ingest-manifest), design.md tests 1-8."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

import pytest
from sqlalchemy import select

from wordsworth.anonymizer import DeterministicAnonymizer
from wordsworth.ingest_corpus import main
from wordsworth.ingest_manifest import ManifestResult, ingest_manifest_corpus
from wordsworth.manifest import ManifestError, write_record
from wordsworth.models import AuditRecord, Document
from wordsworth.openanonymiser_driver import AnonymizationEngineError
from wordsworth.pipeline import current_state, ingest as pipeline_ingest
from wordsworth.states import State


def test_missing_corpus_dir_exits_nonzero_without_backends(tmp_path):
    missing = tmp_path / "does-not-exist"
    # Returns before wiring S3/OpenAnonymiser/OpenSearch/Ollama — no creds needed.
    assert main(["--corpus-dir", str(missing), "--dossier", "zaak"]) == 2


# --- manifest path: fixtures -------------------------------------------------

def _pilot_report(tmp_path, decision: str = "proceed", **overrides) -> "Path":
    report = {
        "who": "odin", "when": "2026-10-24T09:00:00+00:00",
        "robots": "Disallow: /niet-hier", "terms": "geen voorwaardenpagina gevonden",
        "anubis": "geen proof-of-work-uitdaging aangetroffen", "decision": decision,
    }
    report.update(overrides)
    path = tmp_path / "check.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    return path


def _entry(filename: str, data: bytes, url: str, fetched_at: str) -> dict:
    return {"file": filename, "url": url, "fetched_at": fetched_at,
            "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
            "status": "fetched", "ok": True}


def _manifest(path, entries: list[dict]) -> "Path":
    with path.open("w", encoding="utf-8") as fh:
        for e in entries:
            write_record(fh, **e)
    return path


class _DownAnonymizer:
    """Always unreachable, the way OpenAnonymiser is when the pod is down."""

    def anonymize(self, text: str):
        raise AnonymizationEngineError("OpenAnonymiser unreachable")


# --- test 1: provenance reaches the register audit record -------------------

def test_manifest_ingest_records_provenance(
    session_factory, tmp_path, born_digital_pdf, mem_store, mem_index, fake_embedder,
    monkeypatch,
):
    monkeypatch.setenv("WORDSWORTH_BACKEND_ENV", "homelab")
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "a.pdf").write_bytes(born_digital_pdf)
    fetched_at = "2026-09-23T10:00:00+00:00"
    manifest = _manifest(
        tmp_path / "manifest.jsonl",
        [_entry("a.pdf", born_digital_pdf, "https://gooisemeren.nl/a.pdf", fetched_at)],
    )
    report = _pilot_report(tmp_path)

    results = ingest_manifest_corpus(
        corpus, "pilot-gooise-meren", manifest, report,
        session_factory=session_factory, store=mem_store,
        anonymizer=DeterministicAnonymizer(), index=mem_index, embedder=fake_embedder,
    )
    assert len(results) == 1
    assert results[0].ok and results[0].state == State.INDEXED

    with session_factory() as session:
        doc = session.execute(
            select(Document).where(Document.filename == "a.pdf")
        ).scalar_one()
        payload = session.execute(
            select(AuditRecord.payload).where(
                AuditRecord.document_id == doc.id, AuditRecord.step == "register"
            )
        ).scalar_one()
        assert payload["source_url"] == "https://gooisemeren.nl/a.pdf"
        assert payload["fetched_at"] == datetime.fromisoformat(fetched_at).isoformat()


# --- test 2: a manifest written the way the fetcher writes it ---------------

def test_fetcher_written_manifest_is_ingested(
    session_factory, tmp_path, born_digital_pdf, mem_store, mem_index, fake_embedder,
    monkeypatch,
):
    monkeypatch.setenv("WORDSWORTH_BACKEND_ENV", "homelab")
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "b.pdf").write_bytes(born_digital_pdf)
    digest = hashlib.sha256(born_digital_pdf).hexdigest()
    manifest_path = tmp_path / "manifest.jsonl"
    with manifest_path.open("w", encoding="utf-8") as fh:
        # Mirrors fetch_woo_corpus.py: the shared fields plus a fetcher's own
        # extra bookkeeping key, which the reader must tolerate.
        write_record(
            fh, file="b.pdf", url="https://gooisemeren.nl/b.pdf",
            fetched_at="2026-09-23T10:05:00+00:00", sha256=digest,
            bytes=len(born_digital_pdf), status="fetched", ok=True,
            besluit="https://gooisemeren.nl/politieke-avond",
        )
    report = _pilot_report(tmp_path)

    results = ingest_manifest_corpus(
        corpus, "pilot-gooise-meren", manifest_path, report,
        session_factory=session_factory, store=mem_store,
        anonymizer=DeterministicAnonymizer(), index=mem_index, embedder=fake_embedder,
    )
    assert results == [ManifestResult("b.pdf", ok=True, state=State.INDEXED, reason=None)]


# --- test 3: an unlisted file aborts the whole run ---------------------------

def test_unlisted_file_aborts_the_run(
    session_factory, tmp_path, born_digital_pdf, mem_store, mem_index, fake_embedder,
    monkeypatch,
):
    monkeypatch.setenv("WORDSWORTH_BACKEND_ENV", "homelab")
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "listed.pdf").write_bytes(born_digital_pdf)
    (corpus / "unlisted.pdf").write_bytes(born_digital_pdf + b"\n%extra-bytes")
    manifest = _manifest(
        tmp_path / "manifest.jsonl",
        [_entry("listed.pdf", born_digital_pdf, "https://gooisemeren.nl/listed.pdf",
                "2026-09-23T10:00:00+00:00")],
    )
    report = _pilot_report(tmp_path)

    with pytest.raises(ManifestError, match="unlisted.pdf"):
        ingest_manifest_corpus(
            corpus, "zaak", manifest, report, session_factory=session_factory,
            store=mem_store, anonymizer=DeterministicAnonymizer(), index=mem_index,
            embedder=fake_embedder,
        )

    with session_factory() as session:
        assert session.execute(select(Document)).first() is None


# --- test 4: a sha256 mismatch fails loudly ----------------------------------

def test_sha256_mismatch_fails_loudly(
    session_factory, tmp_path, born_digital_pdf, mem_store, mem_index, fake_embedder,
    monkeypatch,
):
    monkeypatch.setenv("WORDSWORTH_BACKEND_ENV", "homelab")
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "c.pdf").write_bytes(born_digital_pdf)
    wrong_digest = "0" * 64
    manifest_path = tmp_path / "manifest.jsonl"
    with manifest_path.open("w", encoding="utf-8") as fh:
        write_record(fh, file="c.pdf", url="https://gooisemeren.nl/c.pdf",
                     fetched_at="2026-09-23T10:00:00+00:00", sha256=wrong_digest,
                     bytes=len(born_digital_pdf), status="fetched", ok=True)
    report = _pilot_report(tmp_path)
    real_digest = hashlib.sha256(born_digital_pdf).hexdigest()

    with pytest.raises(ManifestError) as excinfo:
        ingest_manifest_corpus(
            corpus, "zaak", manifest_path, report, session_factory=session_factory,
            store=mem_store, anonymizer=DeterministicAnonymizer(), index=mem_index,
            embedder=fake_embedder,
        )
    message = str(excinfo.value)
    assert "c.pdf" in message and wrong_digest in message and real_digest in message

    with session_factory() as session:
        assert session.execute(select(Document)).first() is None


# --- test 5: a duplicate key fails the read-back, same dossier and another --

def test_duplicate_bytes_fail_readback_in_either_dossier(
    session_factory, tmp_path, born_digital_pdf, mem_store, mem_index, fake_embedder,
    monkeypatch,
):
    monkeypatch.setenv("WORDSWORTH_BACKEND_ENV", "homelab")
    # These bytes are already a document, with no recorded provenance — the
    # 567-document dossier the proposal names.
    with session_factory() as session:
        pipeline_ingest(session, mem_store, born_digital_pdf, dossier="gooise-meren-woo-2022")
        session.commit()
    report = _pilot_report(tmp_path)

    corpus_a = tmp_path / "corpus-a"
    corpus_a.mkdir()
    (corpus_a / "d.pdf").write_bytes(born_digital_pdf)
    manifest_a = _manifest(
        tmp_path / "manifest-a.jsonl",
        [_entry("d.pdf", born_digital_pdf, "https://gooisemeren.nl/d.pdf",
                "2026-09-23T10:00:00+00:00")],
    )
    results_a = ingest_manifest_corpus(
        corpus_a, "pilot-gooise-meren", manifest_a, report,
        session_factory=session_factory, store=mem_store,
        anonymizer=DeterministicAnonymizer(), index=mem_index, embedder=fake_embedder,
    )
    assert len(results_a) == 1
    assert not results_a[0].ok and "source_url" in results_a[0].reason

    # Delivered again, into yet another dossier: still the same bytes, still fails.
    corpus_b = tmp_path / "corpus-b"
    corpus_b.mkdir()
    (corpus_b / "e.pdf").write_bytes(born_digital_pdf)
    manifest_b = _manifest(
        tmp_path / "manifest-b.jsonl",
        [_entry("e.pdf", born_digital_pdf, "https://gooisemeren.nl/e.pdf",
                "2026-09-23T10:05:00+00:00")],
    )
    results_b = ingest_manifest_corpus(
        corpus_b, "another-case", manifest_b, report,
        session_factory=session_factory, store=mem_store,
        anonymizer=DeterministicAnonymizer(), index=mem_index, embedder=fake_embedder,
    )
    assert len(results_b) == 1 and not results_b[0].ok


# --- test 6: a non-homelab or missing backend is refused ---------------------

@pytest.mark.parametrize("value", [None, "", "alma"])
def test_non_homelab_backend_refused(tmp_path, value, monkeypatch):
    if value is None:
        monkeypatch.delenv("WORDSWORTH_BACKEND_ENV", raising=False)
    else:
        monkeypatch.setenv("WORDSWORTH_BACKEND_ENV", value)
    with pytest.raises(ManifestError, match="homelab"):
        ingest_manifest_corpus(tmp_path, "zaak", tmp_path / "no-manifest.jsonl",
                               tmp_path / "no-report.json")


# --- test 7: OpenAnonymiser down fails the run -------------------------------

def test_openanonymiser_down_fails_the_run(
    session_factory, tmp_path, born_digital_pdf, mem_store, mem_index, fake_embedder,
    monkeypatch,
):
    monkeypatch.setenv("WORDSWORTH_BACKEND_ENV", "homelab")
    monkeypatch.setenv("WORDSWORTH_RETRY_BASE_DELAY", "0")  # no real sleeps
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "f.pdf").write_bytes(born_digital_pdf)
    manifest = _manifest(
        tmp_path / "manifest.jsonl",
        [_entry("f.pdf", born_digital_pdf, "https://gooisemeren.nl/f.pdf",
                "2026-09-23T10:00:00+00:00")],
    )
    report = _pilot_report(tmp_path)

    results = ingest_manifest_corpus(
        corpus, "pilot-gooise-meren", manifest, report,
        session_factory=session_factory, store=mem_store,
        anonymizer=_DownAnonymizer(), index=mem_index, embedder=fake_embedder,
    )
    rc = 0 if results and all(r.ok for r in results) else 1
    assert rc == 1
    assert mem_index._docs == {}  # nothing indexed

    with session_factory() as session:
        doc = session.execute(
            select(Document).where(Document.filename == "f.pdf")
        ).scalar_one()
        # anonymize does not commit EXTRACTED; the document stays REGISTERED.
        assert current_state(session, doc.id) == State.REGISTERED


# --- test 8: a pilot report without a completed check is refused ------------

def test_pilot_report_without_completed_check_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("WORDSWORTH_BACKEND_ENV", "homelab")
    incomplete = tmp_path / "check.json"
    incomplete.write_text(
        json.dumps({"who": "odin", "when": "2026-10-24T09:00:00+00:00",
                   "decision": "proceed"}),
        encoding="utf-8",
    )
    with pytest.raises(ManifestError, match="missing"):
        ingest_manifest_corpus(tmp_path, "zaak", tmp_path / "no-manifest.jsonl", incomplete)


def test_pilot_report_decision_other_than_proceed_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("WORDSWORTH_BACKEND_ENV", "homelab")
    report = _pilot_report(tmp_path, decision="stop")
    with pytest.raises(ManifestError, match="stop"):
        ingest_manifest_corpus(tmp_path, "zaak", tmp_path / "no-manifest.jsonl", report)
