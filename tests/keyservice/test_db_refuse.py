"""design.md "Refuse to start": the three rules, and that both the server
and the init entrypoint actually call the check (not merely that the check
itself is correct)."""
from __future__ import annotations

import pytest

from wordsworth.keyservice import bootstrap, serve
from wordsworth.keyservice.db import (RefuseToStart, check_openbao_refuse_to_start,
                                      check_pseudonymise_cap_refuse_to_start,
                                      check_refuse_to_start)
from wordsworth.transit import FakeTransit


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


def test_openbao_refuses_empty_url():
    with pytest.raises(RefuseToStart, match="KEYSERVICE_OPENBAO_URL"):
        check_openbao_refuse_to_start("", "a-token")


def test_openbao_refuses_empty_token():
    with pytest.raises(RefuseToStart, match="KEYSERVICE_OPENBAO_TOKEN"):
        check_openbao_refuse_to_start("http://bao:8200", "")


def test_openbao_allows_both_set():
    check_openbao_refuse_to_start("http://bao:8200", "a-token")  # does not raise


def test_openbao_ignores_wordsworths_settings(monkeypatch):
    # design.md "Settings and the Transit seam": KEYSERVICE_* only, no
    # fallback to WORDSWORTH_* -- exercised here through the check itself,
    # which never reads any environment variable at all.
    monkeypatch.setenv("WORDSWORTH_OPENBAO_URL", "http://wordsworth-bao:8200")
    monkeypatch.setenv("WORDSWORTH_OPENBAO_TOKEN", "wordsworth-token")
    check_openbao_refuse_to_start("http://keyservice-bao:8200", "keyservice-token")


def test_cap_refuses_above_ceiling():
    with pytest.raises(RefuseToStart, match="KEYSERVICE_PSEUDONYMISE_MAX_ITEMS"):
        check_pseudonymise_cap_refuse_to_start(5001)


def test_cap_allows_the_ceiling():
    check_pseudonymise_cap_refuse_to_start(5000)  # does not raise


def test_server_startup_calls_the_openbao_check_when_transit_for_is_none(
        keyservice_database_url, monkeypatch):
    monkeypatch.setenv("KEYSERVICE_DATABASE_URL", keyservice_database_url)
    monkeypatch.delenv("WORDSWORTH_DATABASE_URL", raising=False)
    monkeypatch.delenv("KEYSERVICE_OPENBAO_URL", raising=False)
    monkeypatch.delenv("KEYSERVICE_OPENBAO_TOKEN", raising=False)
    app = serve.create_app(service_tokens={})
    from fastapi.testclient import TestClient

    with pytest.raises(RefuseToStart, match="KEYSERVICE_OPENBAO_URL"):
        with TestClient(app):
            pass


def test_server_startup_skips_the_openbao_check_when_transit_for_is_passed(
        keyservice_database_url, monkeypatch):
    monkeypatch.setenv("KEYSERVICE_DATABASE_URL", keyservice_database_url)
    monkeypatch.delenv("WORDSWORTH_DATABASE_URL", raising=False)
    monkeypatch.delenv("KEYSERVICE_OPENBAO_URL", raising=False)
    monkeypatch.delenv("KEYSERVICE_OPENBAO_TOKEN", raising=False)
    app = serve.create_app(service_tokens={}, transit_for=lambda kek: FakeTransit())
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200


def test_init_entrypoint_calls_the_openbao_check(monkeypatch):
    monkeypatch.delenv("KEYSERVICE_OPENBAO_URL", raising=False)
    monkeypatch.delenv("KEYSERVICE_OPENBAO_TOKEN", raising=False)
    monkeypatch.setattr(bootstrap, "check_refuse_to_start", lambda url: None)
    with pytest.raises(RefuseToStart, match="KEYSERVICE_OPENBAO_URL"):
        bootstrap.main()
