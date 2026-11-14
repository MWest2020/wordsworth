"""Guards around the thin client's API key (#445 review).

A key that cannot go into a header is refused before any request, without
echoing it; a key headed for a plain-http remote host gets a warning; and a
redirect, which never carries the key, is named in the 401 hint."""
from __future__ import annotations

import http.server
import threading

import pytest

import wordsworth.client as client
from wordsworth.client import main

SECRET = "sk_secret"


@pytest.fixture
def no_net(monkeypatch, tmp_path):
    monkeypatch.delenv("WORDSWORTH_API_KEY", raising=False)
    monkeypatch.setattr(client, "CONFIG_PATH", tmp_path / "config.yaml")
    calls = []

    def fake_urlopen(req, timeout=0):
        calls.append(req)

        class R:
            def read(self):
                return b"{}"

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False
        return R()

    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)
    return calls


@pytest.mark.parametrize("bad", [
    "sk_secret\nXYZ",          # a second line from $(cat keyfile)
    "sk_secret€XYZ",      # euro sign: outside latin-1
    "sk_secret XYZ",           # whitespace inside
    "sk_secret\x1bXYZ",        # control character (ESC)
])
def test_unusable_env_key_is_refused_without_echoing_it(no_net, monkeypatch,
                                                         capsys, bad):
    monkeypatch.setenv("WORDSWORTH_API_KEY", bad)
    assert main(["--url", "http://localhost:8000", "state", "d1"]) == 2
    out, err = capsys.readouterr()
    assert no_net == []                              # nothing went out
    assert "$WORDSWORTH_API_KEY is not a usable API key" in err
    assert "not shown" in err
    assert SECRET not in out + err and "XYZ" not in out + err
    assert "Traceback" not in err


def test_unusable_config_key_names_the_config_file(no_net, capsys):
    client.CONFIG_PATH.write_text("api_key: sk_secret\x07XYZ\n")
    assert main(["--url", "http://localhost:8000", "state", "d1"]) == 2
    _, err = capsys.readouterr()
    assert "api_key in the config file" in err and SECRET not in err


def test_latin1_key_with_surrounding_newline_is_fine(no_net, monkeypatch):
    monkeypatch.setenv("WORDSWORTH_API_KEY", "\nsk_sécret\n")
    assert main(["--url", "http://localhost:8000", "state", "d1"]) == 0
    assert no_net[0].get_header("X-api-key") == "sk_sécret"


@pytest.mark.parametrize("url,warned", [
    ("http://wordsworth-api.example", True),
    ("https://wordsworth-api.example", False),
    ("http://localhost:8000", False),
    ("http://127.0.0.1:8000", False),
])
def test_plain_http_to_a_remote_host_warns(no_net, monkeypatch, capsys,
                                           url, warned):
    monkeypatch.setenv("WORDSWORTH_API_KEY", SECRET)
    assert main(["--url", url, "state", "d1"]) == 0
    _, err = capsys.readouterr()
    assert ("goes out in clear" in err) is warned
    assert SECRET not in err


def test_plain_http_without_a_key_does_not_warn(no_net, capsys):
    assert main(["--url", "http://wordsworth-api.example", "state", "d1"]) == 0
    assert "in clear" not in capsys.readouterr().err


class _Api(http.server.BaseHTTPRequestHandler):
    seen: list = []

    def do_GET(self):
        _Api.seen.append((self.server.server_port, self.headers.get("X-API-Key")))
        if self.server.redirect_to:
            self.send_response(302)
            self.send_header("Location", self.server.redirect_to + self.path)
            self.end_headers()
            return
        ok = self.headers.get("X-API-Key") == SECRET
        self.send_response(200 if ok else 401)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"{}" if ok else b'{"detail":"invalid or missing API key"}')

    def log_message(self, *a):
        pass


def _serve(redirect_to=None):
    srv = http.server.HTTPServer(("127.0.0.1", 0), _Api)
    srv.redirect_to = redirect_to
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def test_redirect_drops_the_key_and_the_hint_says_so(monkeypatch, tmp_path,
                                                     capsys):
    """A real redirect over the wire: the key reaches the first server only,
    and the 401 from the second one points at the URL to use instead."""
    monkeypatch.setattr(client, "CONFIG_PATH", tmp_path / "config.yaml")
    monkeypatch.setenv("WORDSWORTH_API_KEY", SECRET)
    target = _serve()
    front = _serve(f"http://127.0.0.1:{target.server_port}")
    _Api.seen = []
    try:
        code = main(["--url", f"http://127.0.0.1:{front.server_port}",
                     "state", "d1"])
    finally:
        front.shutdown()
        target.shutdown()
    _, err = capsys.readouterr()
    assert code == 1
    assert _Api.seen == [(front.server_port, SECRET), (target.server_port, None)]
    assert f"redirected to http://127.0.0.1:{target.server_port}" in err
    assert "use that (https) URL directly" in err
    assert SECRET not in err
