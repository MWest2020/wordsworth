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


def test_grant_issue_posts_expected_payload(monkeypatch):
    seen = {}
    monkeypatch.setattr(client, "_post_json",
                        lambda base, path, payload, timeout=30: seen.update(
                            path=path, payload=payload) or {"grant_id": "g1"})
    assert main(["--url", "http://api", "grant", "issue",
                 "--recipient", "team-a", "--types", "PERSON,EMAIL",
                 "--document", "d1", "--expires", "2026-12-31T00:00:00+00:00"]) == 0
    assert seen["path"] == "/grants"
    assert seen["payload"] == {"recipient": "team-a",
                               "allowed_types": ["PERSON", "EMAIL"],
                               "document_id": "d1",
                               "expires_at": "2026-12-31T00:00:00+00:00"}


def test_grant_show_gets_by_id(monkeypatch):
    seen = {}
    monkeypatch.setattr(client, "_get",
                        lambda base, path: seen.update(path=path) or {"status": "active"})
    assert main(["--url", "http://api", "grant", "show", "g42"]) == 0
    assert seen["path"] == "/grants/g42"


def test_grant_revoke_posts_revoke(monkeypatch):
    seen = {}
    monkeypatch.setattr(client, "_post_json",
                        lambda base, path, payload, timeout=30: seen.update(
                            path=path, payload=payload) or {"status": "revoked"})
    assert main(["--url", "http://api", "grant", "revoke", "g42"]) == 0
    assert seen["path"] == "/grants/g42/revoke" and seen["payload"] == {}


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


def test_ingest_retries_batch_then_continues(tmp_path, monkeypatch):
    import urllib.error
    for n in ("a.pdf", "b.pdf"):
        (tmp_path / n).write_bytes(b"%PDF-1.4")
    calls = {"n": 0}

    def fake_post(url, paths, timeout=600):
        calls["n"] += 1
        if calls["n"] == 1:
            raise urllib.error.URLError("timed out")  # batch1 attempt1 fails...
        return {"results": [{"filename": paths[0].name, "state": "indexed"}]}

    monkeypatch.setattr(client, "_post_files", fake_post)
    monkeypatch.setattr(client.time, "sleep", lambda s: None)  # no real backoff
    # batch=1 → two batches; batch1 fails once then its retry succeeds.
    rc = main(["--url", "http://x", "ingest", str(tmp_path), "--batch", "1",
               "--retries", "3"])
    assert calls["n"] == 3   # b1 attempt1 (fail) + b1 attempt2 (ok) + b2 (ok)
    assert rc == 0           # retry recovered the batch → all indexed


def test_ingest_counts_skipped_as_not_failed(tmp_path, monkeypatch, capsys):
    for n in ("a.pdf", "b.pdf"):
        (tmp_path / n).write_bytes(b"%PDF-1.4")

    def fake_post(url, paths, timeout=600):
        return {"results": [{"filename": p.name,
                             "state": "skipped" if p.name == "a.pdf" else "indexed"}
                            for p in paths]}

    monkeypatch.setattr(client, "_post_files", fake_post)
    rc = main(["--url", "http://x", "ingest", str(tmp_path), "--batch", "5"])
    out = capsys.readouterr().out
    assert "1/2 indexed, 1 skipped, 0 failed" in out
    assert rc == 0   # skipped is not a failure


def test_ingest_reports_failed_files_after_retries_exhausted(tmp_path, monkeypatch):
    import urllib.error
    (tmp_path / "x.pdf").write_bytes(b"%PDF-1.4")

    def always_fail(url, paths, timeout=600):
        raise urllib.error.URLError("down")

    monkeypatch.setattr(client, "_post_files", always_fail)
    monkeypatch.setattr(client.time, "sleep", lambda s: None)
    rc = main(["--url", "http://x", "ingest", str(tmp_path), "--retries", "2"])
    assert rc == 1  # exhausted → file reported failed, run still completes


def test_ingest_survives_non_json_response(tmp_path, monkeypatch):
    (tmp_path / "x.pdf").write_bytes(b"%PDF-1.4")

    def bad_json(url, paths, timeout=600):
        raise ValueError("Expecting value: line 1 column 1")  # proxy error page

    monkeypatch.setattr(client, "_post_files", bad_json)
    monkeypatch.setattr(client.time, "sleep", lambda s: None)
    # Must NOT raise (previously a ValueError crashed the whole ingest).
    rc = main(["--url", "http://x", "ingest", str(tmp_path), "--retries", "2"])
    assert rc == 1


def test_result_extra_formats_duration_and_counts():
    extra = client._result_extra(
        {"state": "indexed", "duration_ms": 1834.0,
         "counts": {"person": 2, "bsn": 1, "iban": 0}})
    assert extra == " (1.8s, bsn=1 person=2)"   # sorted, zero-counts dropped
    assert client._result_extra({"state": "error", "error": "OcrError"}) == " (OcrError)"
    assert client._result_extra({"state": "indexed"}) == ""


class _FakeResp:
    def __init__(self, data: bytes):
        self._d = data

    def read(self) -> bytes:
        return self._d

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_export_docs_downloads_zip(tmp_path, monkeypatch):
    seen = {}

    def fake_urlopen(url, timeout=0):
        seen["url"] = url
        return _FakeResp(b"PK\x03\x04zip")

    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)
    out = tmp_path / "corpus.zip"
    assert main(["--url", "http://api", "export", "docs", str(out)]) == 0
    assert seen["url"] == "http://api/export/anonymized.zip"
    assert out.read_bytes() == b"PK\x03\x04zip"


def test_export_ranking_downloads_csv(tmp_path, monkeypatch):
    seen = {}

    def fake_urlopen(url, timeout=0):
        seen["url"] = url
        return _FakeResp(b"rank,document_id,score,object_key\n1,d1,9.0,k1\n")

    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)
    out = tmp_path / "ranking.csv"
    assert main(["--url", "http://api", "export", "ranking", "parkeren", str(out)]) == 0
    assert seen["url"].startswith("http://api/export/ranking.csv?")
    assert "query=parkeren" in seen["url"]
    assert out.read_bytes().startswith(b"rank,document_id")
