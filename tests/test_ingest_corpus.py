"""Corpus-ingestion CLI guards — offline (no backends contacted).

The manifest guards here need no database or sovereign backend either: each
one raises before `ingest_manifest_corpus` wires anything (pilot-ingest-
manifest). The DB-integration tests (provenance read-back, duplicate
delivery, a layer that did not run) live in `test_ingest_manifest.py`.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from wordsworth.ingest_corpus import main
from wordsworth.ingest_manifest import (
    require_completed_pilot_check,
    require_homelab_backend,
)
from wordsworth.manifest import ManifestError


def test_missing_corpus_dir_exits_nonzero_without_backends(tmp_path):
    missing = tmp_path / "does-not-exist"
    # Returns before wiring S3/OpenAnonymiser/OpenSearch/Ollama — no creds needed.
    assert main(["--corpus-dir", str(missing), "--dossier", "zaak"]) == 2


def test_manifest_without_pilot_report_exits_nonzero(tmp_path):
    assert main(["--corpus-dir", str(tmp_path), "--dossier", "zaak",
                "--manifest", str(tmp_path / "manifest.jsonl")]) == 2


@pytest.mark.parametrize("value", [None, "", "alma", "productie"])
def test_require_homelab_backend_refuses_non_homelab(value, monkeypatch):
    if value is None:
        monkeypatch.delenv("WORDSWORTH_BACKEND_ENV", raising=False)
    else:
        monkeypatch.setenv("WORDSWORTH_BACKEND_ENV", value)
    with pytest.raises(ManifestError, match="homelab"):
        require_homelab_backend()


def test_require_homelab_backend_accepts_homelab(monkeypatch):
    monkeypatch.setenv("WORDSWORTH_BACKEND_ENV", "homelab")
    require_homelab_backend()  # does not raise


def _report(tmp_path, **overrides) -> Path:
    report = {
        "checked_by": "odin", "checked_at": "2026-10-23T18:00:00+00:00",
        "robots_txt": "User-agent: *\nAllow: /", "terms": "no terms page found",
        "anubis": "not present", "decision": "proceed",
        **overrides,
    }
    path = tmp_path / "check.json"
    path.write_text(json.dumps(report))
    return path


def test_pilot_check_passes_when_complete(tmp_path):
    require_completed_pilot_check(_report(tmp_path))  # does not raise


@pytest.mark.parametrize("missing_field", [
    "checked_by", "checked_at", "robots_txt", "terms", "anubis",
])
def test_pilot_check_refuses_an_incomplete_report(tmp_path, missing_field):
    report = {
        "checked_by": "odin", "checked_at": "2026-10-23T18:00:00+00:00",
        "robots_txt": "User-agent: *\nAllow: /", "terms": "no terms page found",
        "anubis": "not present", "decision": "proceed",
    }
    del report[missing_field]
    path = tmp_path / "check.json"
    path.write_text(json.dumps(report))
    with pytest.raises(ManifestError, match="no completed check"):
        require_completed_pilot_check(path)


def test_pilot_check_refuses_a_decision_that_is_not_proceed(tmp_path):
    with pytest.raises(ManifestError, match="not 'proceed'"):
        require_completed_pilot_check(_report(tmp_path, decision="stop"))


def test_pilot_check_refuses_an_unreadable_report(tmp_path):
    with pytest.raises(ManifestError):
        require_completed_pilot_check(tmp_path / "does-not-exist.json")


def test_main_exits_nonzero_when_manifest_run_is_refused(tmp_path, monkeypatch):
    monkeypatch.delenv("WORDSWORTH_BACKEND_ENV", raising=False)  # refused, not defaulted
    assert main(["--corpus-dir", str(tmp_path), "--dossier", "zaak",
                "--manifest", str(tmp_path / "manifest.jsonl"),
                "--pilot-report", str(tmp_path / "check.json")]) == 1
