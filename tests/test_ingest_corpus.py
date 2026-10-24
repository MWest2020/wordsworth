"""Corpus-ingestion CLI guards — offline (no backends contacted)."""
from __future__ import annotations

import json

from wordsworth.ingest_corpus import main


def test_missing_corpus_dir_exits_nonzero_without_backends(tmp_path):
    missing = tmp_path / "does-not-exist"
    # Returns before wiring S3/OpenAnonymiser/OpenSearch/Ollama — no creds needed.
    assert main(["--corpus-dir", str(missing), "--dossier", "zaak"]) == 2


def _write_check(directory):
    check = {
        "checked_by": "odin", "checked_at": "2026-10-24T08:00:00+00:00",
        "robots_txt_url": "https://example.nl/robots.txt",
        "robots_txt": "User-agent: *\nAllow: /",
        "paths_used": ["/woo-documenten"], "paths_disallowed_used": [],
        "terms": "https://example.nl/terms", "anubis": "not present",
        "user_agent": "wordsworth-pilot/0.1", "delay_seconds": 1.0,
        "decision": "proceed",
    }
    (directory / "check.json").write_text(json.dumps(check), encoding="utf-8")


# task 6 ("Verification"), the automatable part: `--manifest` refuses before
# any backend is wired, for each of the three ways a manifest run is unsafe —
# no live S3/OpenAnonymiser/OpenSearch/Ollama needed to prove any of them.

def test_manifest_run_refused_with_unset_backend_env(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("WORDSWORTH_BACKEND_ENV", raising=False)
    (tmp_path / "manifest.jsonl").write_text("", encoding="utf-8")
    rc = main(["--corpus-dir", str(tmp_path), "--dossier", "zaak",
              "--manifest", str(tmp_path / "manifest.jsonl")])
    assert rc == 1
    assert "WORDSWORTH_BACKEND_ENV" in capsys.readouterr().err


def test_manifest_run_refused_with_alma_backend_env(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("WORDSWORTH_BACKEND_ENV", "alma")
    (tmp_path / "manifest.jsonl").write_text("", encoding="utf-8")
    rc = main(["--corpus-dir", str(tmp_path), "--dossier", "zaak",
              "--manifest", str(tmp_path / "manifest.jsonl")])
    assert rc == 1
    assert "WORDSWORTH_BACKEND_ENV" in capsys.readouterr().err


def test_manifest_run_refused_for_unlisted_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("WORDSWORTH_BACKEND_ENV", "homelab")
    _write_check(tmp_path)
    (tmp_path / "unlisted.pdf").write_bytes(b"whatever bytes")
    (tmp_path / "manifest.jsonl").write_text("", encoding="utf-8")  # lists nothing
    rc = main(["--corpus-dir", str(tmp_path), "--dossier", "zaak",
              "--manifest", str(tmp_path / "manifest.jsonl")])
    assert rc == 1
    assert "unlisted.pdf" in capsys.readouterr().err
