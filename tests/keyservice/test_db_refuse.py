"""design.md "Refuse to start": the three rules, and that both the server
and the init entrypoint actually call the check (not merely that the check
itself is correct)."""
from __future__ import annotations

import pytest

from wordsworth.keyservice import bootstrap, serve
from wordsworth.keyservice.db import RefuseToStart, check_refuse_to_start


def test_rule1_refuses_empty_url():
    with pytest.raises(RefuseToStart, match="rule 1"):
        check_refuse_to_start("")


def test_rule2_refuses_same_database_as_wordsworth(keyservice_database_url, monkeypatch):
    monkeypatch.setenv("WORDSWORTH_DATABASE_URL", keyservice_database_url)
    with pytest.raises(RefuseToStart, match="rule 2"):
        check_refuse_to_start(keyservice_database_url)


def test_rule2_allows_a_different_database(keyservice_database_url, database_url, monkeypatch):
    monkeypatch.setenv("WORDSWORTH_DATABASE_URL", database_url)
    check_refuse_to_start(keyservice_database_url)  # does not raise


def test_rule3_refuses_a_database_holding_wordsworth_tables(
        database_url, session_factory, monkeypatch):
    # `session_factory` (the repo-wide fixture) has already created
    # wordsworth's tables in `database_url`.
    monkeypatch.delenv("WORDSWORTH_DATABASE_URL", raising=False)
    with pytest.raises(RefuseToStart, match="rule 3"):
        check_refuse_to_start(database_url)


def test_rule3_allows_a_clean_database(keyservice_database_url, monkeypatch):
    monkeypatch.delenv("WORDSWORTH_DATABASE_URL", raising=False)
    check_refuse_to_start(keyservice_database_url)  # does not raise


def test_server_startup_calls_the_check(monkeypatch):
    def boom(url):
        raise RefuseToStart("rule 1: boom")

    monkeypatch.setattr(serve, "check_refuse_to_start", boom)
    app = serve.create_app()
    from fastapi.testclient import TestClient

    with pytest.raises(RefuseToStart):
        with TestClient(app):
            pass


def test_init_entrypoint_calls_the_check(monkeypatch):
    def boom(url):
        raise RefuseToStart("rule 1: boom")

    monkeypatch.setattr(bootstrap, "check_refuse_to_start", boom)
    with pytest.raises(RefuseToStart):
        bootstrap.main()
