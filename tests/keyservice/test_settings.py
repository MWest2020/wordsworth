"""KEYSERVICE_* settings are their own thing, never wordsworth's
WORDSWORTH_* (design.md "Settings")."""
from __future__ import annotations

from wordsworth.keyservice.config import Settings


def test_database_url_ignores_wordsworth_settings(monkeypatch):
    monkeypatch.setenv("WORDSWORTH_DATABASE_URL", "postgresql+psycopg://x/wordsworth")
    monkeypatch.setenv("KEYSERVICE_DATABASE_URL", "postgresql+psycopg://x/keyservice")
    settings = Settings()
    assert settings.database_url == "postgresql+psycopg://x/keyservice"


def test_database_url_empty_without_env(monkeypatch):
    monkeypatch.delenv("KEYSERVICE_DATABASE_URL", raising=False)
    monkeypatch.setenv("WORDSWORTH_DATABASE_URL", "postgresql+psycopg://x/wordsworth")
    settings = Settings()
    assert settings.database_url == ""


def test_service_tokens_empty_by_default(monkeypatch):
    monkeypatch.delenv("KEYSERVICE_SERVICE_TOKENS", raising=False)
    assert Settings().service_tokens == {}


def test_service_tokens_parsed_label_token_pairs(monkeypatch):
    monkeypatch.setenv("KEYSERVICE_SERVICE_TOKENS", "ingest:tok-a,search:tok-b")
    assert Settings().service_tokens == {"tok-a": "ingest", "tok-b": "search"}
