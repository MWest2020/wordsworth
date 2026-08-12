"""Corpus-ingestion CLI guards — offline (no backends contacted)."""
from __future__ import annotations

from wordsworth.ingest_corpus import main


def test_missing_corpus_dir_exits_nonzero_without_backends(tmp_path):
    missing = tmp_path / "does-not-exist"
    # Returns before wiring S3/OpenAnonymiser/OpenSearch/Ollama — no creds needed.
    assert main(["--corpus-dir", str(missing)]) == 2
