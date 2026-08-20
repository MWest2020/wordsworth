"""Reversible-mode wiring — pure/local (no DB, no OpenBao) (add-wire-reversible-mode).

Proves the config flag defaults off, the reveal route mounts only when the
session-scoped factories are supplied, and `serve.build_app` flips both by config
without any network I/O at import."""
from __future__ import annotations

from wordsworth.api import create_app
from wordsworth.config import Settings
from wordsworth.db import make_engine, make_session_factory

REVEAL = "/documents/{document_id}/reveal"


def _paths(app):
    return {r.path for r in app.routes}


def test_reversible_mode_defaults_off(monkeypatch):
    monkeypatch.delenv("WORDSWORTH_REVERSIBLE", raising=False)
    assert Settings().reversible_mode is False


def test_default_app_has_no_reveal_route():
    sf = make_session_factory(make_engine())
    assert REVEAL not in _paths(create_app(session_factory=sf))


def test_factories_mount_the_reveal_route():
    sf = make_session_factory(make_engine())
    app = create_app(
        session_factory=sf,
        key_provider_factory=lambda s: None,   # mount check only; not called here
        grant_store_factory=lambda s: None,
    )
    assert REVEAL in _paths(app)


def test_build_app_off_has_no_reveal(monkeypatch):
    monkeypatch.setenv("WORDSWORTH_REVERSIBLE", "false")
    monkeypatch.delenv("WORDSWORTH_S3_ACCESS_KEY", raising=False)
    monkeypatch.delenv("WORDSWORTH_S3_SECRET_KEY", raising=False)
    from wordsworth.serve import build_app

    assert REVEAL not in _paths(build_app())


def test_build_app_on_mounts_reveal(monkeypatch):
    monkeypatch.setenv("WORDSWORTH_REVERSIBLE", "true")
    from wordsworth.serve import build_app

    # No OpenBao/S3 I/O happens at build — factories are only called per request.
    assert REVEAL in _paths(build_app())
