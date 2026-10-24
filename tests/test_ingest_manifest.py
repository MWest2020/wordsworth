"""pilot-ingest-manifest: `ingest_corpus.py --manifest`, design.md's tests.

The seam the reviewer requires: these call `ingest_manifest_corpus` end to
end, not just the manifest parser in isolation (a parser test alone proved
nothing when `register_live()` silently kept an existing document's old
provenance -- see design.md, "the clever pitfall").
"""
from __future__ import annotations

import hashlib
import json

from sqlalchemy import select

from wordsworth.anonymizer import DeterministicAnonymizer
from wordsworth.audit import current_state
from wordsworth.manifest import CheckError, ManifestError, load_check, manifest_line
from wordsworth.models import AuditRecord
from wordsworth.openanonymiser_driver import AnonymizationEngineError
from wordsworth.pipeline import ingest
from wordsworth.states import State

from wordsworth.ingest_manifest import (
    BackendGuardError,
    Sha256MismatchError,
    UnlistedFileError,
    ingest_manifest_corpus,
    require_homelab_backend,
)

FETCHED_AT = "2026-10-24T09:00:00+00:00"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_check(directory, **overrides):
    check = {
        "checked_by": "odin", "checked_at": "2026-10-24T08:00:00+00:00",
        "robots_txt_url": "https://example.nl/robots.txt",
        "robots_txt": "User-agent: *\nAllow: /",
        "paths_used": ["/woo-documenten"], "paths_disallowed_used": [],
        "terms": "https://example.nl/terms", "anubis": "not present",
        "user_agent": "wordsworth-pilot/0.1", "delay_seconds": 1.0,
        "decision": "proceed",
    }
    check.update(overrides)
    (directory / "check.json").write_text(json.dumps(check), encoding="utf-8")
    return check


def _write_manifest(directory, entries: list[dict]) -> None:
    lines = [manifest_line(file=e["file"], url=e["url"],
                            fetched_at=e.get("fetched_at", FETCHED_AT),
                            sha256=e["sha256"], bytes_=e["bytes"],
                            status=e.get("status", 200), ok=e.get("ok", True))
              for e in entries]
    (directory / "manifest.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _put_pdf(directory, name: str, data: bytes):
    (directory / name).write_bytes(data)
    return {"file": name, "url": f"https://media.example.nl/{name}",
            "sha256": _sha256(data), "bytes": len(data)}


def _register_payload(session, document_id):
    return session.execute(
        select(AuditRecord.payload)
        .where(AuditRecord.document_id == document_id, AuditRecord.step == "register")
        .order_by(AuditRecord.seq).limit(1)
    ).scalar_one()


# --- the pilot check gate (design test 9) -----------------------------------

def test_check_gate_missing_file_is_refused(tmp_path):
    try:
        load_check(tmp_path / "manifest.jsonl")
        assert False, "expected CheckError"
    except CheckError as exc:
        assert "check.json" in str(exc) and "not found" in str(exc)


def test_check_gate_missing_field_is_refused(tmp_path):
    check = _write_check(tmp_path)
    del check["anubis"]
    (tmp_path / "check.json").write_text(json.dumps(check), encoding="utf-8")
    try:
        load_check(tmp_path / "manifest.jsonl")
        assert False, "expected CheckError"
    except CheckError as exc:
        assert "anubis" in str(exc)


def test_check_gate_disallowed_path_is_refused(tmp_path):
    _write_check(tmp_path, paths_disallowed_used=["/admin"])
    try:
        load_check(tmp_path / "manifest.jsonl")
        assert False, "expected CheckError"
    except CheckError as exc:
        assert "paths_disallowed_used" in str(exc)


def test_check_gate_non_proceed_decision_is_refused(tmp_path):
    _write_check(tmp_path, decision="stop")
    try:
        load_check(tmp_path / "manifest.jsonl")
        assert False, "expected CheckError"
    except CheckError as exc:
        assert "stop" in str(exc)


def test_check_gate_complete_check_passes(tmp_path):
    check = _write_check(tmp_path)
    assert load_check(tmp_path / "manifest.jsonl") == check


# --- backend guard (design test 6) ------------------------------------------

def test_missing_backend_env_is_refused(monkeypatch):
    monkeypatch.delenv("WORDSWORTH_BACKEND_ENV", raising=False)
    try:
        require_homelab_backend()
        assert False, "expected BackendGuardError"
    except BackendGuardError:
        pass


def test_alma_backend_env_is_refused(monkeypatch):
    monkeypatch.setenv("WORDSWORTH_BACKEND_ENV", "alma")
    try:
        require_homelab_backend()
        assert False, "expected BackendGuardError"
    except BackendGuardError:
        pass


def test_backend_guard_runs_before_any_filesystem_access(monkeypatch, tmp_path):
    monkeypatch.delenv("WORDSWORTH_BACKEND_ENV", raising=False)
    missing = tmp_path / "does-not-exist"
    try:
        ingest_manifest_corpus(missing, "dossier", missing / "manifest.jsonl")
        assert False, "expected BackendGuardError"
    except BackendGuardError:
        pass  # not FileNotFoundError: the guard runs before any path is touched


# --- pre-flight checks (design tests 3 and 4) -------------------------------

def test_unlisted_file_aborts_before_any_ingest(monkeypatch, tmp_path):
    monkeypatch.setenv("WORDSWORTH_BACKEND_ENV", "homelab")
    _write_check(tmp_path)
    listed = _put_pdf(tmp_path, "listed.pdf", b"listed-bytes")
    _put_pdf(tmp_path, "unlisted.pdf", b"unlisted-bytes")  # no manifest entry
    _write_manifest(tmp_path, [listed])
    try:
        ingest_manifest_corpus(tmp_path, "dossier", tmp_path / "manifest.jsonl")
        assert False, "expected UnlistedFileError"
    except UnlistedFileError as exc:
        assert "unlisted.pdf" in str(exc)


def test_sha256_mismatch_fails_loudly(monkeypatch, tmp_path):
    monkeypatch.setenv("WORDSWORTH_BACKEND_ENV", "homelab")
    _write_check(tmp_path)
    entry = _put_pdf(tmp_path, "doc.pdf", b"real-bytes")
    entry["sha256"] = "0" * 64
    _write_manifest(tmp_path, [entry])
    try:
        ingest_manifest_corpus(tmp_path, "dossier", tmp_path / "manifest.jsonl")
        assert False, "expected Sha256MismatchError"
    except Sha256MismatchError as exc:
        assert "doc.pdf" in str(exc) and "0" * 64 in str(exc)


def test_manifest_missing_a_required_field_is_refused(monkeypatch, tmp_path):
    monkeypatch.setenv("WORDSWORTH_BACKEND_ENV", "homelab")
    _write_check(tmp_path)
    (tmp_path / "manifest.jsonl").write_text(
        json.dumps({"file": "doc.pdf", "url": "https://x", "sha256": "a" * 64}) + "\n",
        encoding="utf-8")
    try:
        ingest_manifest_corpus(tmp_path, "dossier", tmp_path / "manifest.jsonl")
        assert False, "expected ManifestError"
    except ManifestError as exc:
        assert "fetched_at" in str(exc)


# --- end-to-end through the real pipeline (design tests 1, 2, 5, 7) --------

def test_provenance_reaches_the_audit_record(
    monkeypatch, tmp_path, born_digital_pdf, session_factory, mem_store, mem_index,
    fake_embedder,
):
    monkeypatch.setenv("WORDSWORTH_BACKEND_ENV", "homelab")
    _write_check(tmp_path)
    entry = _put_pdf(tmp_path, "doc.pdf", born_digital_pdf)
    _write_manifest(tmp_path, [entry])

    outcomes = ingest_manifest_corpus(
        tmp_path, "pilot-dossier", tmp_path / "manifest.jsonl",
        session_factory=session_factory, store=mem_store,
        anonymizer=DeterministicAnonymizer(), search_index=mem_index,
        embedder=fake_embedder,
    )

    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert outcome.ok is True
    assert outcome.state == State.INDEXED

    with session_factory() as session:
        from wordsworth.models import Document
        doc = session.execute(select(Document).where(Document.filename == "doc.pdf")).scalars().one()
        payload = _register_payload(session, doc.id)
        assert payload["source_url"] == entry["url"]
        assert payload["fetched_at"] == FETCHED_AT


def test_fetcher_written_manifest_line_is_ingested(
    monkeypatch, tmp_path, born_digital_pdf, session_factory, mem_store, mem_index,
    fake_embedder,
):
    """A line carrying the fetcher's OLD herkomst keys next to the shared
    manifest fields (how `fetch_woo_corpus.py` writes it) still parses and
    ingests -- extra fields are not an error."""
    monkeypatch.setenv("WORDSWORTH_BACKEND_ENV", "homelab")
    _write_check(tmp_path)
    (tmp_path / "doc.pdf").write_bytes(born_digital_pdf)
    row = {
        "bestand": "doc.pdf", "bron": "https://media.example.nl/doc.pdf",
        "besluit": "https://example.nl/besluit", "bytes": len(born_digital_pdf),
        "opgehaald": FETCHED_AT,
        "file": "doc.pdf", "url": "https://media.example.nl/doc.pdf",
        "fetched_at": FETCHED_AT, "sha256": _sha256(born_digital_pdf),
        "status": 200, "ok": True,
    }
    (tmp_path / "manifest.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")

    outcomes = ingest_manifest_corpus(
        tmp_path, "pilot-dossier", tmp_path / "manifest.jsonl",
        session_factory=session_factory, store=mem_store,
        anonymizer=DeterministicAnonymizer(), search_index=mem_index,
        embedder=fake_embedder,
    )
    assert outcomes[0].ok is True


def test_duplicate_key_fails_with_the_reason(
    monkeypatch, tmp_path, born_digital_pdf, session_factory, mem_store, mem_index,
    fake_embedder,
):
    monkeypatch.setenv("WORDSWORTH_BACKEND_ENV", "homelab")
    with session_factory() as session:
        ingest(session, mem_store, born_digital_pdf, filename="dup.pdf",
               dossier="dossier-a")  # no provenance -- the existing-corpus case
        session.commit()

    _write_check(tmp_path)
    entry = _put_pdf(tmp_path, "dup.pdf", born_digital_pdf)
    _write_manifest(tmp_path, [entry])

    for dossier in ("dossier-a", "dossier-b"):  # same dossier, and another one
        outcomes = ingest_manifest_corpus(
            tmp_path, dossier, tmp_path / "manifest.jsonl",
            session_factory=session_factory, store=mem_store,
            anonymizer=DeterministicAnonymizer(), search_index=mem_index,
            embedder=fake_embedder,
        )
        assert outcomes[0].ok is False
        assert "source_url" in outcomes[0].reason


def test_openanonymiser_down_fails_the_run_and_stays_registered(
    monkeypatch, tmp_path, born_digital_pdf, session_factory, mem_store, mem_index,
    fake_embedder,
):
    monkeypatch.setenv("WORDSWORTH_BACKEND_ENV", "homelab")
    monkeypatch.setenv("WORDSWORTH_RETRY_ATTEMPTS", "1")  # no retry sleep
    _write_check(tmp_path)
    entry = _put_pdf(tmp_path, "doc.pdf", born_digital_pdf)
    _write_manifest(tmp_path, [entry])

    class _DownAnonymizer:
        def anonymize(self, text: str):
            raise AnonymizationEngineError("OpenAnonymiser unreachable")

    outcomes = ingest_manifest_corpus(
        tmp_path, "pilot-dossier", tmp_path / "manifest.jsonl",
        session_factory=session_factory, store=mem_store,
        anonymizer=_DownAnonymizer(), search_index=mem_index, embedder=fake_embedder,
    )

    assert len(outcomes) == 1
    assert outcomes[0].ok is False
    assert mem_index._docs == {}  # nothing indexed

    with session_factory() as session:
        from wordsworth.models import Document
        doc = session.execute(select(Document).where(Document.filename == "doc.pdf")).scalars().one()
        # A failed anonymize never commits EXTRACTED (process() only commits
        # after a step's audit record is written); the document stays at the
        # last state that DID commit.
        assert current_state(session, doc.id) == State.REGISTERED
