"""wordsworthctl client — offline bits (no server contacted)."""
from __future__ import annotations

import wordsworth.client as client
from wordsworth.client import _iter_files, main


def test_iter_files_pdf_recursive_and_all(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "note.txt").write_text("x")

    pdfs = _iter_files(tmp_path, include_all=False)
    assert {p.name for p in pdfs} == {"a.pdf", "b.pdf"}  # recursive, pdf-only

    everything = _iter_files(tmp_path, include_all=True)
    assert {p.name for p in everything} == {"a.pdf", "b.pdf", "note.txt"}


def test_iter_files_single_file(tmp_path):
    f = tmp_path / "only.pdf"
    f.write_bytes(b"%PDF-1.4")
    assert _iter_files(f, include_all=False) == [f]


def test_ingest_missing_path_exits_nonzero(tmp_path):
    assert main(["--url", "http://unused", "ingest", str(tmp_path / "nope")]) == 2


def test_config_write_and_resolve(tmp_path, monkeypatch):
    monkeypatch.setattr(client, "CONFIG_PATH", tmp_path / "config.yaml")
    monkeypatch.delenv("WORDSWORTH_API_URL", raising=False)
    assert main(["config", "--url", "http://api:8000", "--batch", "5"]) == 0
    cfg = client._load_config()
    assert cfg["url"] == "http://api:8000" and cfg["batch"] == "5"
    assert client._resolve_url(None, cfg) == "http://api:8000"   # config used
    assert client._resolve_url("http://flag", cfg) == "http://flag"  # flag wins


def test_resolve_url_env_beats_config(monkeypatch):
    monkeypatch.setenv("WORDSWORTH_API_URL", "http://env:8000")
    assert client._resolve_url(None, {"url": "http://cfg:8000"}) == "http://env:8000"


def test_ingest_continues_after_a_batch_timeout(tmp_path, monkeypatch):
    import urllib.error
    for n in ("a.pdf", "b.pdf"):
        (tmp_path / n).write_bytes(b"%PDF-1.4")
    calls = {"n": 0}

    def fake_post(url, paths, timeout=600):
        calls["n"] += 1
        if calls["n"] == 1:
            raise urllib.error.URLError("timed out")          # first batch fails
        return {"results": [{"filename": paths[0].name, "state": "indexed"}]}

    monkeypatch.setattr(client, "_post_files", fake_post)
    # batch=1 → two batches; the timeout on batch 1 must not abort batch 2.
    rc = main(["--url", "http://x", "ingest", str(tmp_path), "--batch", "1"])
    assert calls["n"] == 2   # both batches attempted despite the first timing out
    assert rc == 1           # one file failed → non-zero, but the run completed


def test_result_extra_formats_duration_and_counts():
    extra = client._result_extra(
        {"state": "indexed", "duration_ms": 1834.0,
         "counts": {"person": 2, "bsn": 1, "iban": 0}})
    assert extra == " (1.8s, bsn=1 person=2)"   # sorted, zero-counts dropped
    assert client._result_extra({"state": "error", "error": "OcrError"}) == " (OcrError)"
    assert client._result_extra({"state": "indexed"}) == ""
