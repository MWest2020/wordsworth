"""Corpus-ingestion CLI guards — offline (no backends contacted)."""
from __future__ import annotations

import hashlib
import json

import wordsworth.ingest_corpus as ingest_corpus_mod
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


# --- task 3.1: a refusing key service exits non-zero, does not go on -------

def _refusing_from(n: int):
    """A transit factory sharing one counter and one working inner transit:
    `wrap` (used by `mint`, once per new object) refuses from the n-th call
    on; `unwrap` always succeeds, so a file minted before the refusal still
    reads back fine."""
    from wordsworth.transit import FakeTransit

    inner = FakeTransit()
    calls = [0]

    class _Transit:
        def wrap(self, plaintext: bytes) -> bytes:
            calls[0] += 1
            if calls[0] >= n:
                raise RuntimeError("key service down")
            return inner.wrap(plaintext)

        def unwrap(self, ciphertext: bytes) -> bytes:
            return inner.unwrap(ciphertext)

    return lambda name: _Transit()


def _wire_fake_backends(monkeypatch, session_factory, store, mem_index, fake_embedder):
    """Swap `ingest_corpus()`'s real backend constructors for test doubles.
    originals-ingest-switch moved the CLI's store-building through
    `originals_io.originals_from_config` (`ingest_corpus()` no longer uses the
    bare `S3ObjectStore.from_config()` result directly), so that is the seam a
    test stubs to hand `ingest_corpus()` an already-built `OriginalsStore`
    (here, one wrapping a refusing transit) without touching `ingest_corpus()`
    itself."""
    from wordsworth.anonymizer import DeterministicAnonymizer
    from wordsworth.object_store import InMemoryObjectStore

    monkeypatch.setattr(ingest_corpus_mod, "make_engine", lambda: object())
    monkeypatch.setattr(ingest_corpus_mod, "make_session_factory",
                        lambda engine: session_factory)

    class _FakeS3:
        @classmethod
        def from_config(cls):
            return InMemoryObjectStore()  # discarded: originals_from_config is stubbed below

    class _FakeIndex:
        @classmethod
        def from_config(cls):
            return mem_index

    class _FakeEmbedder:
        @classmethod
        def from_config(cls):
            return fake_embedder

    monkeypatch.setattr(ingest_corpus_mod, "S3ObjectStore", _FakeS3)
    monkeypatch.setattr(ingest_corpus_mod, "originals_from_config", lambda raw_store: store)
    monkeypatch.setattr(ingest_corpus_mod, "OpenAnonymiserAnonymizer",
                        lambda: DeterministicAnonymizer())
    monkeypatch.setattr(ingest_corpus_mod, "OpenSearchIndex", _FakeIndex)
    monkeypatch.setattr(ingest_corpus_mod, "OllamaEmbedder", _FakeEmbedder)


def test_ingest_corpus_exits_nonzero_on_key_refusal_and_stops(
    tmp_path, monkeypatch, capsys, session_factory, mem_index, fake_embedder,
):
    from wordsworth.document_keys import DocumentKeys
    from wordsworth.object_store import InMemoryObjectStore
    from wordsworth.originals_store import OriginalsStore

    for i in range(1, 4):
        (tmp_path / f"{i}.pdf").write_bytes(f"bytes for file {i}".encode())

    store = OriginalsStore(InMemoryObjectStore(), DocumentKeys(_refusing_from(2)))
    _wire_fake_backends(monkeypatch, session_factory, store, mem_index, fake_embedder)

    rc = main(["--corpus-dir", str(tmp_path), "--dossier", "zaak"])

    assert rc == 1
    assert "key service unavailable" in capsys.readouterr().err
    # file 1 (sorted first) wrote through; files 2 and 3 never attempted a write.
    key1 = "documents/" + hashlib.sha256(b"bytes for file 1").hexdigest()
    key2 = "documents/" + hashlib.sha256(b"bytes for file 2").hexdigest()
    key3 = "documents/" + hashlib.sha256(b"bytes for file 3").hexdigest()
    assert store.objects.exists(key1)
    assert not store.objects.exists(key2)
    assert not store.objects.exists(key3)


def test_manifest_run_exits_nonzero_on_key_refusal(
    tmp_path, monkeypatch, capsys,
):
    from wordsworth.document_keys import OriginalsKeyUnavailable

    monkeypatch.setenv("WORDSWORTH_BACKEND_ENV", "homelab")
    (tmp_path / "manifest.jsonl").write_text("", encoding="utf-8")

    def _boom(*args, **kwargs):
        raise OriginalsKeyUnavailable("key service down")

    monkeypatch.setattr("wordsworth.ingest_manifest.ingest_manifest_corpus", _boom)

    rc = main(["--corpus-dir", str(tmp_path), "--dossier", "zaak",
              "--manifest", str(tmp_path / "manifest.jsonl")])

    assert rc == 1
    assert capsys.readouterr().err.strip() == "key service unavailable"
