"""Production corpus ingestion: CLI guards (offline) and pilot-ingest-manifest
(design.md's numbered tests 1-8; the DB-backed ones run against real Postgres,
skip locally without one)."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from wordsworth.anonymizer import DeterministicAnonymizer
from wordsworth.backend_guard import BackendGuardError
from wordsworth.ingest_corpus import ingest_manifest_corpus, main
from wordsworth.manifest import ManifestError, append_entry
from wordsworth.models import Document
from wordsworth.openanonymiser_driver import AnonymizationEngineError
from wordsworth.pilot_report import PilotReportError
from wordsworth.pipeline import ingest, register_payload
from wordsworth.states import State


def test_missing_corpus_dir_exits_nonzero_without_backends(tmp_path):
    missing = tmp_path / "does-not-exist"
    # Returns before wiring S3/OpenAnonymiser/OpenSearch/Ollama — no creds needed.
    assert main(["--corpus-dir", str(missing), "--dossier", "zaak"]) == 2


def test_manifest_requires_pilot_report(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text("")
    assert main(["--corpus-dir", str(corpus), "--dossier", "zaak",
                "--manifest", str(manifest)]) == 2


# --- shared fixtures ---------------------------------------------------------

PROCEED_REPORT = {
    "who": "odin", "when": "2026-10-24T09:00:00+00:00",
    "robots_txt": "User-agent: *\nAllow: /", "terms": "no terms page found",
    "anubis_status": "not present", "decision": "proceed",
}


@pytest.fixture
def pilot_report(tmp_path) -> Path:
    path = tmp_path / "check.json"
    path.write_text(json.dumps(PROCEED_REPORT))
    return path


@pytest.fixture
def homelab_env(monkeypatch):
    """Declares every backend as homelab -- the guard this change adds would
    otherwise refuse every manifest test, same as a real deployment must
    declare it (see design.md, 'Settled')."""
    monkeypatch.setenv("WORDSWORTH_HOMELAB_HOSTS", "lab.local")
    monkeypatch.setenv("WORDSWORTH_S3_ENDPOINT_URL", "http://s3.lab.local:8333")
    monkeypatch.setenv("WORDSWORTH_OPENANONYMISER_URL",
                       "http://openanonymiser.lab.local:8080")
    monkeypatch.setenv("WORDSWORTH_OPENSEARCH_URL", "http://opensearch.lab.local:9200")
    monkeypatch.setenv("WORDSWORTH_OLLAMA_URL", "http://ollama.lab.local:11434")


def _write_pdf(path: Path, data: bytes) -> str:
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


# --- test 3: a file without an entry aborts the run (offline) --------------

def test_unlisted_file_aborts_before_any_ingest(tmp_path, born_digital_pdf,
                                                pilot_report, homelab_env):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "a.pdf").write_bytes(born_digital_pdf)
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text("")  # no entries at all

    with pytest.raises(ManifestError, match="a.pdf"):
        ingest_manifest_corpus(corpus, "zaak", manifest, pilot_report)


# --- test 4: a file that is not the one the manifest describes (offline) ---

def test_sha256_mismatch_fails_loudly(tmp_path, born_digital_pdf, pilot_report,
                                      homelab_env):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "a.pdf").write_bytes(born_digital_pdf)
    manifest = tmp_path / "manifest.jsonl"
    append_entry(manifest, filename="a.pdf", url="https://example.nl/a.pdf",
                fetched_at=datetime(2026, 10, 20, 9, 30, tzinfo=timezone.utc),
                sha256="0" * 64)

    with pytest.raises(ManifestError, match="sha256 mismatch"):
        ingest_manifest_corpus(corpus, "zaak", manifest, pilot_report)


# --- test 6: missing and non-homelab backend refused, alma included --------

def test_missing_backend_refused(tmp_path, born_digital_pdf, pilot_report, monkeypatch):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    digest = _write_pdf(corpus / "a.pdf", born_digital_pdf)
    manifest = tmp_path / "manifest.jsonl"
    append_entry(manifest, filename="a.pdf", url="https://example.nl/a.pdf",
                fetched_at=datetime(2026, 10, 20, 9, 30, tzinfo=timezone.utc),
                sha256=digest)
    monkeypatch.delenv("WORDSWORTH_S3_ENDPOINT_URL", raising=False)  # not configured

    with pytest.raises(BackendGuardError, match="object store"):
        ingest_manifest_corpus(corpus, "zaak", manifest, pilot_report)


def test_non_homelab_backend_refused_alma_included(tmp_path, born_digital_pdf,
                                                     pilot_report, homelab_env,
                                                     monkeypatch):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    digest = _write_pdf(corpus / "a.pdf", born_digital_pdf)
    manifest = tmp_path / "manifest.jsonl"
    append_entry(manifest, filename="a.pdf", url="https://example.nl/a.pdf",
                fetched_at=datetime(2026, 10, 20, 9, 30, tzinfo=timezone.utc),
                sha256=digest)
    # homelab_env declared the other three homelab; this one points at alma's
    # real in-cluster svc-DNS (config.py's own example for that URL).
    monkeypatch.setenv(
        "WORDSWORTH_OPENANONYMISER_URL",
        "http://openanonymiser.openanonymiser.svc.cluster.local:8080")

    with pytest.raises(BackendGuardError, match="OpenAnonymiser"):
        ingest_manifest_corpus(corpus, "zaak", manifest, pilot_report)


# --- test 8: a manifest needs a completed pilot check (offline) ------------

def test_pilot_report_without_completed_check_is_refused(tmp_path, born_digital_pdf,
                                                           homelab_env):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    digest = _write_pdf(corpus / "a.pdf", born_digital_pdf)
    manifest = tmp_path / "manifest.jsonl"
    append_entry(manifest, filename="a.pdf", url="https://example.nl/a.pdf",
                fetched_at=datetime(2026, 10, 20, 9, 30, tzinfo=timezone.utc),
                sha256=digest)
    incomplete = tmp_path / "check.json"
    incomplete.write_text(json.dumps({**PROCEED_REPORT, "robots_txt": ""}))

    with pytest.raises(PilotReportError, match="completed check"):
        ingest_manifest_corpus(corpus, "zaak", manifest, incomplete)


def test_pilot_report_decision_stop_is_refused(tmp_path, born_digital_pdf, homelab_env):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    digest = _write_pdf(corpus / "a.pdf", born_digital_pdf)
    manifest = tmp_path / "manifest.jsonl"
    append_entry(manifest, filename="a.pdf", url="https://example.nl/a.pdf",
                fetched_at=datetime(2026, 10, 20, 9, 30, tzinfo=timezone.utc),
                sha256=digest)
    stopped = tmp_path / "check.json"
    stopped.write_text(json.dumps({**PROCEED_REPORT, "decision": "stop"}))

    with pytest.raises(PilotReportError, match="stop"):
        ingest_manifest_corpus(corpus, "zaak", manifest, stopped)


# --- DB-backed: tests 1, 2, 5, 7 (real Postgres; skip without one) ---------

def test_provenance_reaches_the_audit_record(tmp_path, born_digital_pdf, pilot_report,
                                             homelab_env, session_factory, mem_store,
                                             mem_index, fake_embedder):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    digest = _write_pdf(corpus / "a.pdf", born_digital_pdf)
    fetched_at = datetime(2026, 10, 20, 9, 30, tzinfo=timezone.utc)
    manifest = tmp_path / "manifest.jsonl"
    append_entry(manifest, filename="a.pdf", url="https://gooisemeren.nl/a.pdf",
                fetched_at=fetched_at, sha256=digest)

    results = ingest_manifest_corpus(
        corpus, "zaak", manifest, pilot_report, session_factory=session_factory,
        store=mem_store, anonymizer=DeterministicAnonymizer(),
        index=mem_index, embedder=fake_embedder)

    assert results == [("a.pdf", State.INDEXED)]
    with session_factory() as session:
        doc = session.execute(select(Document)).scalar_one()
        payload = register_payload(session, doc.id)
        assert payload["source_url"] == "https://gooisemeren.nl/a.pdf"
        assert payload["fetched_at"] == fetched_at.isoformat()


def test_fetcher_written_manifest_is_ingested(tmp_path, born_digital_pdf, pilot_report,
                                              homelab_env, session_factory, mem_store,
                                              mem_index, fake_embedder):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "0001_besluit.pdf").write_bytes(born_digital_pdf)
    digest = hashlib.sha256(born_digital_pdf).hexdigest()
    manifest = tmp_path / "manifest.jsonl"
    # The way fetch_woo_corpus.py writes it: manifest.append_entry, with its
    # own extra fields (besluit, bytes) alongside the shared three.
    append_entry(
        manifest, filename="0001_besluit.pdf",
        url="https://open.gelderland.nl/0001_besluit.pdf",
        fetched_at=datetime.now(timezone.utc), sha256=digest,
        extra={"besluit": "https://open.gelderland.nl/woo-documenten/x",
               "bytes": len(born_digital_pdf)},
    )

    results = ingest_manifest_corpus(
        corpus, "zaak", manifest, pilot_report, session_factory=session_factory,
        store=mem_store, anonymizer=DeterministicAnonymizer(),
        index=mem_index, embedder=fake_embedder)

    assert results == [("0001_besluit.pdf", State.INDEXED)]


def test_duplicate_key_same_dossier_fails_with_reason(tmp_path, born_digital_pdf,
                                                        pilot_report, homelab_env,
                                                        session_factory, mem_store,
                                                        mem_index, fake_embedder):
    with session_factory() as session:
        ingest(session, mem_store, born_digital_pdf, dossier="zaak",
              source_url="https://other.nl/old.pdf",
              fetched_at=datetime(2020, 1, 1, tzinfo=timezone.utc))
        session.commit()

    corpus = tmp_path / "corpus"
    corpus.mkdir()
    digest = _write_pdf(corpus / "a.pdf", born_digital_pdf)
    manifest = tmp_path / "manifest.jsonl"
    append_entry(manifest, filename="a.pdf", url="https://gooisemeren.nl/a.pdf",
                fetched_at=datetime(2026, 10, 20, 9, 30, tzinfo=timezone.utc),
                sha256=digest)

    results = ingest_manifest_corpus(
        corpus, "zaak", manifest, pilot_report, session_factory=session_factory,
        store=mem_store, anonymizer=DeterministicAnonymizer(),
        index=mem_index, embedder=fake_embedder)

    assert results == [("a.pdf", State.FAILED)]


def test_duplicate_key_another_dossier_fails_with_reason(tmp_path, born_digital_pdf,
                                                          pilot_report, homelab_env,
                                                          session_factory, mem_store,
                                                          mem_index, fake_embedder):
    with session_factory() as session:
        ingest(session, mem_store, born_digital_pdf, dossier="other-dossier")
        session.commit()

    corpus = tmp_path / "corpus"
    corpus.mkdir()
    digest = _write_pdf(corpus / "a.pdf", born_digital_pdf)
    manifest = tmp_path / "manifest.jsonl"
    append_entry(manifest, filename="a.pdf", url="https://gooisemeren.nl/a.pdf",
                fetched_at=datetime(2026, 10, 20, 9, 30, tzinfo=timezone.utc),
                sha256=digest)

    results = ingest_manifest_corpus(
        corpus, "zaak", manifest, pilot_report, session_factory=session_factory,
        store=mem_store, anonymizer=DeterministicAnonymizer(),
        index=mem_index, embedder=fake_embedder)

    assert results == [("a.pdf", State.FAILED)]


def test_rerunning_the_same_manifest_passes_provenance(tmp_path, born_digital_pdf,
                                                        pilot_report, homelab_env,
                                                        session_factory, mem_store,
                                                        mem_index, fake_embedder):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    digest = _write_pdf(corpus / "a.pdf", born_digital_pdf)
    fetched_at = datetime(2026, 10, 20, 9, 30, tzinfo=timezone.utc)
    manifest = tmp_path / "manifest.jsonl"
    append_entry(manifest, filename="a.pdf", url="https://gooisemeren.nl/a.pdf",
                fetched_at=fetched_at, sha256=digest)
    kwargs = dict(session_factory=session_factory, store=mem_store,
                  anonymizer=DeterministicAnonymizer(), index=mem_index,
                  embedder=fake_embedder)

    first = ingest_manifest_corpus(corpus, "zaak", manifest, pilot_report, **kwargs)
    second = ingest_manifest_corpus(corpus, "zaak", manifest, pilot_report, **kwargs)

    assert first == [("a.pdf", State.INDEXED)]
    assert second == [("a.pdf", State.INDEXED)]  # same provenance: not failed


class _AlwaysDown:
    def anonymize(self, text):
        raise AnonymizationEngineError("OpenAnonymiser unreachable")


def test_openanonymiser_down_fails_the_run(tmp_path, born_digital_pdf, pilot_report,
                                           homelab_env, session_factory, mem_store,
                                           mem_index, fake_embedder, monkeypatch):
    monkeypatch.setenv("WORDSWORTH_RETRY_BASE_DELAY", "0")  # no real sleeps
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    digest = _write_pdf(corpus / "a.pdf", born_digital_pdf)
    manifest = tmp_path / "manifest.jsonl"
    append_entry(manifest, filename="a.pdf", url="https://gooisemeren.nl/a.pdf",
                fetched_at=datetime(2026, 10, 20, 9, 30, tzinfo=timezone.utc),
                sha256=digest)

    with pytest.raises(AnonymizationEngineError):
        ingest_manifest_corpus(
            corpus, "zaak", manifest, pilot_report, session_factory=session_factory,
            store=mem_store, anonymizer=_AlwaysDown(), index=mem_index,
            embedder=fake_embedder)

    assert mem_index._docs == {}  # no document reported as indexed
