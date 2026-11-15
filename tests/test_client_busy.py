# SPDX-License-Identifier: MIT
"""The thin client and a 503 from the API (#403): back off and retry a bounded
number of times, then stop the run and report the files as not ingested because
the server was busy -- not as failed files, and not once per later batch."""
import email.message
import io
import json
import urllib.error

from wordsworth import client
from wordsworth.client import main


def _busy(body: bytes, retry_after: str | None = None) -> urllib.error.HTTPError:
    headers = email.message.Message()
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return urllib.error.HTTPError("http://api/ingest", 503, "Service Unavailable",
                                  headers, io.BytesIO(body))


def _files(tmp_path, *names):
    for n in names:
        (tmp_path / n).write_bytes(b"%PDF-1.4")


def _run(tmp_path, monkeypatch, urlopen, *extra):
    sleeps = []
    monkeypatch.setattr(client.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(client.time, "sleep", sleeps.append)
    rc = main(["--url", "http://api", "ingest", str(tmp_path), "--dossier", "d",
               *extra])
    return rc, sleeps


def test_a_503_that_stays_stops_the_run_and_marks_no_file_failed(
        tmp_path, monkeypatch, capsys):
    _files(tmp_path, "a.pdf", "b.pdf", "c.pdf")
    calls = []

    def urlopen(req, timeout=0):
        calls.append(req)
        raise _busy(b"<html>503 from the proxy</html>")

    rc, sleeps = _run(tmp_path, monkeypatch, urlopen, "--batch", "1", "--retries", "3")
    out = capsys.readouterr().out
    assert len(calls) == 3                 # one batch, three attempts; b and c never sent
    assert sleeps == [3, 6]                # backs off between attempts, not after the last
    assert rc == 1
    assert "FAILED" not in out and "failed files" not in out
    for name in ("a.pdf", "b.pdf", "c.pdf"):
        assert f"{name}: NOT INGESTED (server busy)" in out
    assert "0/3 indexed, 0 failed, 3 not ingested (server busy)" in out
    assert "Run the same command again later" in out


def test_a_503_that_passes_is_retried_and_the_run_completes(
        tmp_path, monkeypatch, capsys):
    _files(tmp_path, "a.pdf")
    calls = []

    def urlopen(req, timeout=0):
        calls.append(req)
        if len(calls) == 1:
            raise _busy(b'{"detail": "key service unavailable", "results": []}',
                        retry_after="7")
        return io.BytesIO(json.dumps(
            {"results": [{"filename": "a.pdf", "state": "indexed"}]}).encode())

    rc, sleeps = _run(tmp_path, monkeypatch, urlopen)
    out = capsys.readouterr().out
    assert rc == 0 and len(calls) == 2
    assert sleeps == [7]                   # the server's Retry-After, when it sends one
    assert "HTTP 503 Service Unavailable (key service unavailable)" in out
    assert "1/1 indexed, 0 failed" in out and "not ingested" not in out


def test_files_the_503_reports_as_finished_are_counted_not_lost(
        tmp_path, monkeypatch, capsys):
    """The key-service 503 carries the results of the files done before it."""
    _files(tmp_path, "a.pdf", "b.pdf", "c.pdf")
    body = json.dumps({"detail": "key service unavailable", "total": 2, "indexed": 1,
                       "results": [{"filename": "a.pdf", "state": "indexed"}]}).encode()

    def urlopen(req, timeout=0):
        raise _busy(body)

    rc, _ = _run(tmp_path, monkeypatch, urlopen, "--batch", "2", "--retries", "2")
    out = capsys.readouterr().out
    assert rc == 1
    assert "a.pdf: indexed" in out and "a.pdf: NOT INGESTED" not in out
    assert "b.pdf: NOT INGESTED (server busy)" in out      # same batch, not finished
    assert "c.pdf: NOT INGESTED (server busy)" in out      # later batch, never sent
    assert "1/3 indexed, 0 failed, 2 not ingested (server busy)" in out


def test_a_huge_retry_after_is_capped(tmp_path, monkeypatch):
    _files(tmp_path, "a.pdf")

    def urlopen(req, timeout=0):
        raise _busy(b"", retry_after="86400")

    _, sleeps = _run(tmp_path, monkeypatch, urlopen, "--retries", "2")
    assert sleeps == [60]


def test_another_5xx_is_still_a_failed_batch_and_the_run_goes_on(
        tmp_path, monkeypatch, capsys):
    _files(tmp_path, "a.pdf", "b.pdf")
    calls = []

    def urlopen(req, timeout=0):
        calls.append(req)
        raise urllib.error.HTTPError("http://api/ingest", 500, "Internal Server Error",
                                     email.message.Message(), io.BytesIO(b""))

    rc, _ = _run(tmp_path, monkeypatch, urlopen, "--batch", "1", "--retries", "2")
    out = capsys.readouterr().out
    assert rc == 1 and len(calls) == 4     # both batches tried, as before
    assert "a.pdf: FAILED" in out and "b.pdf: FAILED" in out
    assert "not ingested" not in out
