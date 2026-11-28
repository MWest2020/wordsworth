"""design.md "Stores": the service's own ``MappingStore``/``KeyVaultStore``
over its own models, and ``DurableKeyProvider`` over them (not wordsworth's
stores, which query wordsworth's own models)."""
from __future__ import annotations

from wordsworth.keys import DurableKeyProvider
from wordsworth.keyservice.stores_pii import PostgresKeyVaultStore, PostgresMappingStore
from wordsworth.transit import FakeTransit


def test_mapping_store_put_then_get_round_trips(keyservice_session_factory):
    with keyservice_session_factory() as session:
        store = PostgresMappingStore(session)
        store.put("[PERSON:aaaaaaaa]", b"cipher", b"nonce", "key-1", norm_version="n1")
        session.commit()

        mapping = store.get("[PERSON:aaaaaaaa]")
    assert mapping is not None
    assert mapping.ciphertext == b"cipher"
    assert mapping.nonce == b"nonce"
    assert mapping.key_id == "key-1"
    assert mapping.norm_version == "n1"


def test_mapping_store_put_is_idempotent(keyservice_session_factory):
    with keyservice_session_factory() as session:
        store = PostgresMappingStore(session)
        store.put("[PERSON:aaaaaaaa]", b"first", b"nonce-1", "key-1")
        store.put("[PERSON:aaaaaaaa]", b"second", b"nonce-2", "key-2")
        session.commit()

        mapping = store.get("[PERSON:aaaaaaaa]")
    assert mapping.ciphertext == b"first"
    assert mapping.key_id == "key-1"


def test_mapping_store_get_missing_returns_none(keyservice_session_factory):
    with keyservice_session_factory() as session:
        store = PostgresMappingStore(session)
        assert store.get("[PERSON:ffffffff]") is None


def test_key_vault_store_put_then_active_for(keyservice_session_factory):
    with keyservice_session_factory() as session:
        vault = PostgresKeyVaultStore(session)
        vault.put("key-1", "PERSON", b"wrapped", "active")
        session.commit()

        entry = vault.active_for("PERSON")
    assert entry is not None
    assert entry.key_id == "key-1"
    assert entry.status == "active"


def test_key_vault_store_set_status_retires_a_key(keyservice_session_factory):
    with keyservice_session_factory() as session:
        vault = PostgresKeyVaultStore(session)
        vault.put("key-1", "PERSON", b"wrapped", "active")
        vault.set_status("key-1", "retired")
        session.commit()

        assert vault.active_for("PERSON") is None
        assert vault.get("key-1").status == "retired"


def test_durable_key_provider_over_the_service_stores(keyservice_session_factory):
    """``DurableKeyProvider`` (wordsworth's own) works unchanged over the
    service's own ``KeyVaultStore`` -- design.md "Stores"."""
    with keyservice_session_factory() as session:
        vault = PostgresKeyVaultStore(session)
        provider = DurableKeyProvider(vault, FakeTransit())
        key = provider.current_key(scope="PERSON")
        session.commit()

        again = provider.current_key(scope="PERSON")
    assert again.id == key.id
    assert again.material == key.material
