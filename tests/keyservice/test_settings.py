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


def test_openbao_url_empty_by_default(monkeypatch):
    monkeypatch.delenv("KEYSERVICE_OPENBAO_URL", raising=False)
    assert Settings().openbao_url == ""


def test_openbao_url_ignores_wordsworth_settings(monkeypatch):
    monkeypatch.setenv("WORDSWORTH_OPENBAO_URL", "http://wordsworth:8200")
    monkeypatch.setenv("KEYSERVICE_OPENBAO_URL", "http://keyservice:8200")
    assert Settings().openbao_url == "http://keyservice:8200"


def test_openbao_token_empty_by_default(monkeypatch):
    monkeypatch.delenv("KEYSERVICE_OPENBAO_TOKEN", raising=False)
    assert Settings().openbao_token == ""


def test_openbao_token_ignores_wordsworth_settings(monkeypatch):
    monkeypatch.setenv("WORDSWORTH_OPENBAO_TOKEN", "wordsworth-token")
    monkeypatch.setenv("KEYSERVICE_OPENBAO_TOKEN", "keyservice-token")
    assert Settings().openbao_token == "keyservice-token"


def test_transit_kek_defaults_to_wordsworth(monkeypatch):
    monkeypatch.delenv("KEYSERVICE_TRANSIT_KEK", raising=False)
    assert Settings().transit_kek == "wordsworth"


def test_transit_kek_ignores_wordsworth_settings(monkeypatch):
    monkeypatch.setenv("WORDSWORTH_TRANSIT_KEK", "wordsworth-kek")
    monkeypatch.setenv("KEYSERVICE_TRANSIT_KEK", "keyservice-kek")
    assert Settings().transit_kek == "keyservice-kek"


def test_key_cache_ttl_defaults_to_300(monkeypatch):
    monkeypatch.delenv("KEYSERVICE_KEY_CACHE_TTL", raising=False)
    assert Settings().key_cache_ttl == 300


def test_key_cache_ttl_ignores_wordsworth_settings(monkeypatch):
    monkeypatch.setenv("WORDSWORTH_KEY_CACHE_TTL", "60")
    monkeypatch.setenv("KEYSERVICE_KEY_CACHE_TTL", "120")
    assert Settings().key_cache_ttl == 120


def test_pseudonymise_max_items_defaults_to_1000(monkeypatch):
    monkeypatch.delenv("KEYSERVICE_PSEUDONYMISE_MAX_ITEMS", raising=False)
    assert Settings().pseudonymise_max_items == 1000


def test_pseudonymise_max_items_reads_its_own_setting(monkeypatch):
    monkeypatch.setenv("KEYSERVICE_PSEUDONYMISE_MAX_ITEMS", "250")
    assert Settings().pseudonymise_max_items == 250


def test_originals_kek_defaults_to_transit_kek(monkeypatch):
    monkeypatch.delenv("KEYSERVICE_ORIGINALS_KEK", raising=False)
    monkeypatch.setenv("KEYSERVICE_TRANSIT_KEK", "keyservice-kek")
    assert Settings().originals_kek == "keyservice-kek"


def test_originals_kek_reads_its_own_setting(monkeypatch):
    monkeypatch.setenv("KEYSERVICE_ORIGINALS_KEK", "originals-kek")
    assert Settings().originals_kek == "originals-kek"


def test_originals_kek_by_domain_empty_by_default(monkeypatch):
    monkeypatch.delenv("KEYSERVICE_ORIGINALS_KEK_BY_DOMAIN", raising=False)
    assert Settings().originals_kek_by_domain == {}


def test_originals_kek_by_domain_parses_json(monkeypatch):
    monkeypatch.setenv("KEYSERVICE_ORIGINALS_KEK_BY_DOMAIN", '{"acme": "acme-kek"}')
    assert Settings().originals_kek_by_domain == {"acme": "acme-kek"}


def test_document_key_cache_size_defaults_to_1024(monkeypatch):
    monkeypatch.delenv("KEYSERVICE_DOCUMENT_KEY_CACHE_SIZE", raising=False)
    assert Settings().document_key_cache_size == 1024


def test_document_key_cache_size_reads_its_own_setting(monkeypatch):
    monkeypatch.setenv("KEYSERVICE_DOCUMENT_KEY_CACHE_SIZE", "64")
    assert Settings().document_key_cache_size == 64


def test_open_rate_per_minute_defaults_to_120(monkeypatch):
    monkeypatch.delenv("KEYSERVICE_OPEN_RATE_PER_MINUTE", raising=False)
    assert Settings().open_rate_per_minute == 120


def test_open_rate_per_minute_reads_its_own_setting(monkeypatch):
    monkeypatch.setenv("KEYSERVICE_OPEN_RATE_PER_MINUTE", "60")
    assert Settings().open_rate_per_minute == 60


def test_open_burst_defaults_to_30(monkeypatch):
    monkeypatch.delenv("KEYSERVICE_OPEN_BURST", raising=False)
    assert Settings().open_burst == 30


def test_open_burst_reads_its_own_setting(monkeypatch):
    monkeypatch.setenv("KEYSERVICE_OPEN_BURST", "10")
    assert Settings().open_burst == 10


def test_max_original_bytes_defaults_to_100_mib(monkeypatch):
    monkeypatch.delenv("KEYSERVICE_MAX_ORIGINAL_BYTES", raising=False)
    assert Settings().max_original_bytes == 100 * 1024 * 1024


def test_max_original_bytes_reads_its_own_setting(monkeypatch):
    monkeypatch.setenv("KEYSERVICE_MAX_ORIGINAL_BYTES", "1024")
    assert Settings().max_original_bytes == 1024
