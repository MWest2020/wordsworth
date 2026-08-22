"""Reversible-backfill wiring — pure/local, no DB (add-reversible-backfill).

The /reprocess route mounts only in reversible mode (a session-scoped anonymizer
factory present), and the CLI `reprocess` posts to it."""
from __future__ import annotations

from wordsworth import client
from wordsworth.api import create_app
from wordsworth.db import make_engine, make_session_factory
from wordsworth.search_index import InMemoryIndex

REPROCESS = "/reprocess"


def _paths(app):
    return {r.path for r in app.routes}


def _deps():
    return dict(session_factory=make_session_factory(make_engine()),
                store=object(), search_index=InMemoryIndex(), embedder=object())


def test_reprocess_absent_without_reversible_factory():
    # Ingest deps present but no anonymizer_factory (irreversible) → no backfill.
    assert REPROCESS not in _paths(create_app(**_deps()))


def test_reprocess_mounts_in_reversible_mode():
    app = create_app(**_deps(), anonymizer_factory=lambda s: None)
    assert REPROCESS in _paths(app)


def test_cli_reprocess_all_posts_empty_payload(monkeypatch):
    seen: dict = {}

    def fake(base, path, payload, timeout=3600):
        seen.update(base=base, path=path, payload=payload)
        return {"total": 0, "reanonymized": 0, "skipped": 0,
                "retryable": 0, "failed": 0}

    monkeypatch.setattr(client, "_post_json", fake)
    rc = client.main(["--url", "http://x", "reprocess", "--all"])
    assert rc == 0
    assert seen["path"] == "/reprocess"
    assert seen["payload"] == {}                     # default = all INDEXED


def test_cli_reprocess_ids_payload(monkeypatch):
    seen: dict = {}

    def fake(base, path, payload, timeout=3600):
        seen["payload"] = payload
        return {"total": 2}

    monkeypatch.setattr(client, "_post_json", fake)
    client.main(["--url", "http://x", "reprocess", "--ids", "a, b"])
    assert seen["payload"] == {"document_ids": ["a", "b"]}
