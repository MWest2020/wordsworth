from wordsworth.mapping_store import PostgresMappingStore, write_pending


def test_put_get_roundtrip(session):
    store = PostgresMappingStore(session)
    store.put("[BSN:abcd1234]", b"cipher", b"nonce12bytes", "key1")
    write_pending(session)  # what was put, under the chain lock
    session.commit()
    mapping = store.get("[BSN:abcd1234]")
    assert mapping.ciphertext == b"cipher"
    assert mapping.nonce == b"nonce12bytes"
    assert mapping.key_id == "key1"


def test_put_is_idempotent(session):
    store = PostgresMappingStore(session)
    store.put("[BSN:abcd1234]", b"first", b"n", "k")
    store.put("[BSN:abcd1234]", b"second", b"n", "k")  # ignored
    write_pending(session)  # what was put, under the chain lock
    session.commit()
    assert store.get("[BSN:abcd1234]").ciphertext == b"first"


def test_missing_returns_none(session):
    assert PostgresMappingStore(session).get("[X:00000000]") is None
