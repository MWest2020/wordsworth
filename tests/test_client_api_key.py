"""The thin client sends an API key, and never shows it (#445).

Under caller authentication every route but /health answers 401 without
``X-API-Key``. The key comes from ``$WORDSWORTH_API_KEY`` or ``api_key`` in the
config file — not from a flag, which lands in shell history."""
from __future__ import annotations

import io
import json
import urllib.error
import urllib.request

import pytest

import wordsworth.client as client
from wordsworth.client import main

KEY = "sk_test_do_not_print_4f1c"


class _Resp:
    def __init__(self, data: bytes = b"{}"):
        self._d = data

    def read(self) -> bytes:
        return self._d

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def sent(monkeypatch, tmp_path):
    """Capture every outgoing request; no key in env or config to start with."""
    monkeypatch.delenv("WORDSWORTH_API_KEY", raising=False)
    monkeypatch.setattr(client, "CONFIG_PATH", tmp_path / "config.yaml")
    reqs: list[urllib.request.Request] = []

    def fake_urlopen(req, timeout=0):
        reqs.append(req)
        body = b'{"results": []}' if req.full_url.endswith("/ingest") else b"{}"
        if "pseudonymize" in req.full_url:
            body = b'{"csv": ""}'
        return _Resp(body)

    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)
    return reqs


def _every_transport(tmp_path) -> list[list[str]]:
    """One command per request builder: _get, _post_json, _download,
    _post_files, _post_dataset."""
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    csv = tmp_path / "d.csv"
    csv.write_text("a\n1\n")
    return [
        ["health"],
        ["search", "x", "--dossier", "alle"],
        ["grant", "revoke", "g1"],
        ["export", "docs", str(tmp_path / "out.zip")],
        ["ingest", str(pdf), "--dossier", "d"],
        ["pseudonymize-dataset", str(csv), "--profile-name", "p"],
    ]


def test_key_from_env_is_sent_on_every_request(sent, monkeypatch, tmp_path):
    monkeypatch.setenv("WORDSWORTH_API_KEY", KEY)
    for argv in _every_transport(tmp_path):
        assert main(["--url", "http://api", *argv]) == 0, argv
    assert len(sent) == 6
    assert all(r.get_header("X-api-key") == KEY for r in sent)


def test_no_key_means_no_header(sent, tmp_path):
    for argv in _every_transport(tmp_path):
        assert main(["--url", "http://api", *argv]) == 0, argv
    assert len(sent) == 6
    assert not any(r.has_header("X-api-key") for r in sent)


def test_key_from_config_file_and_env_wins(sent, monkeypatch):
    client.CONFIG_PATH.write_text("url: http://api\napi_key: from-config\n")
    main(["state", "d1"])
    assert sent[-1].get_header("X-api-key") == "from-config"
    monkeypatch.setenv("WORDSWORTH_API_KEY", KEY)
    main(["state", "d1"])
    assert sent[-1].get_header("X-api-key") == KEY


def test_there_is_no_api_key_flag(sent):
    with pytest.raises(SystemExit):
        main(["--api-key", KEY, "health"])


def test_key_is_not_carried_across_a_redirect(monkeypatch):
    """urllib copies ordinary headers onto a redirect to any host."""
    monkeypatch.setattr(client, "_API_KEY", KEY)
    req = client._request("http://api/search")
    new = urllib.request.HTTPRedirectHandler().redirect_request(
        req, None, 302, "Found", {}, "http://elsewhere/")
    assert new is not None and not new.has_header("X-api-key")


def _refuse(code: int, detail: str):
    def fake_urlopen(req, timeout=0):
        raise urllib.error.HTTPError(
            req.full_url, code, "Refused", {},
            io.BytesIO(json.dumps({"detail": detail}).encode()))
    return fake_urlopen


@pytest.mark.parametrize("code,key,hint,not_hint", [
    (401, None, "none was sent: set $WORDSWORTH_API_KEY", "not accepted"),
    (401, KEY, "the key was not accepted", "set $WORDSWORTH_API_KEY"),
    (403, KEY, "the key was accepted, but its caller", "no key was sent"),
    (403, None, "no key was sent", "the key was accepted"),
])
def test_refusal_hint_depends_on_whether_a_key_was_sent(
        sent, monkeypatch, capsys, code, key, hint, not_hint):
    if key:
        monkeypatch.setenv("WORDSWORTH_API_KEY", key)
    monkeypatch.setattr(client.urllib.request, "urlopen",
                        _refuse(code, "server detail"))
    assert main(["--url", "http://localhost:8000", "search", "x",
                 "--dossier", "alle"]) == 1
    out, err = capsys.readouterr()
    assert f"HTTP {code}" in err and "server detail" in err
    assert hint in err and not_hint not in err
    assert KEY not in out + err


def test_ingest_stops_on_401_instead_of_failing_every_batch(sent, monkeypatch,
                                                            capsys, tmp_path):
    for n in range(3):
        (tmp_path / f"{n}.pdf").write_bytes(b"%PDF-1.4")
    monkeypatch.setenv("WORDSWORTH_API_KEY", KEY)
    calls = []

    def refuse(req, timeout=0):
        calls.append(req)
        return _refuse(401, "invalid or missing API key")(req)

    monkeypatch.setattr(client.urllib.request, "urlopen", refuse)
    monkeypatch.setattr(client.time, "sleep", lambda s: None)
    assert main(["--url", "http://api", "ingest", str(tmp_path),
                 "--dossier", "d", "--batch", "1"]) == 1
    out, err = capsys.readouterr()
    assert len(calls) == 1                  # no retries, no further batches
    assert "HTTP 401" in err and "FAILED" not in out
    assert KEY not in out + err


def test_unreachable_api_does_not_show_the_key(sent, monkeypatch, capsys):
    monkeypatch.setenv("WORDSWORTH_API_KEY", KEY)

    def down(req, timeout=0):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(client.urllib.request, "urlopen", down)
    assert main(["--url", "http://api", "state", "d1"]) == 1
    out, err = capsys.readouterr()
    assert "cannot reach" in err and KEY not in out + err


def test_config_show_does_not_print_the_key(sent, capsys):
    client.CONFIG_PATH.write_text(f"url: http://api\napi_key: {KEY}\n")
    assert main(["config", "--show"]) == 0
    assert main(["config", "--batch", "5"]) == 0      # rewrite keeps the key
    out, _ = capsys.readouterr()
    assert "api_key: (set, not shown)" in out and KEY not in out
    assert f"api_key: {KEY}" in client.CONFIG_PATH.read_text()
