"""design.md "The document-key store is the service's own": mint/unwrap over
the service's own ``DocumentKeyRecord``, the bounded+TTL cache, KEK-per-domain,
and ``unwrap``'s classification of a Transit failure into
``KeyBackendUnavailable`` or ``KeyDoesNotUnwrap`` (tasks.md, one test per
case)."""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

import httpx
import pytest

from wordsworth.keyservice.doc_keys import (DocumentKeys, KeyBackendUnavailable,
                                            KeyDoesNotUnwrap, kek_for)
from wordsworth.keyservice.models import DocumentKeyRecord, KnownDocument
from wordsworth.transit import FakeTransit


def _transit_for(name: str) -> FakeTransit:
    return FakeTransit(kek=hashlib.sha256(name.encode()).digest())


def _known(session, domain="acme"):
    doc = KnownDocument(id=uuid.uuid4(), domain=domain,
                        registered_at=datetime.now(timezone.utc))
    session.add(doc)
    session.flush()
    return doc


def test_wordsworth_document_keys_is_absent_from_the_import_graph():
    """design.md "The document-key store is the service's own": the service
    reimplements mint/unwrap/evict over its own model and never imports
    wordsworth's own store -- proved by importing the module in a fresh
    interpreter and checking it never pulled wordsworth.document_keys in."""
    import subprocess
    import sys

    code = (
        "import sys\n"
        "assert 'wordsworth.document_keys' not in sys.modules\n"
        "import wordsworth.keyservice.doc_keys\n"
        "assert 'wordsworth.document_keys' not in sys.modules, "
        "'doc_keys.py must not import wordsworth.document_keys'\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_mint_then_unwrap_round_trips_through_named_transit(keyservice_session_factory):
    with keyservice_session_factory() as session:
        doc = _known(session)
        keys = DocumentKeys(_transit_for)
        minted = keys.mint(session, doc.id, "documents/a", doc.domain)
        session.commit()

        fresh = DocumentKeys(_transit_for)  # cold cache
        unwrapped = fresh.unwrap(session, "documents/a")
    assert unwrapped.key_id == minted.key_id
    assert unwrapped.material == minted.material


def test_row_never_holds_the_clear_dek(keyservice_session_factory):
    with keyservice_session_factory() as session:
        doc = _known(session)
        minted = DocumentKeys(_transit_for).mint(session, doc.id, "documents/a", doc.domain)
        session.commit()
        row = session.get(DocumentKeyRecord, "documents/a")
        assert row.wrapped_material != minted.material
        assert minted.material not in row.wrapped_material


def test_unwrap_with_no_row_raises_key_does_not_unwrap(keyservice_session_factory):
    with keyservice_session_factory() as session:
        with pytest.raises(KeyDoesNotUnwrap):
            DocumentKeys(_transit_for).unwrap(session, "documents/ghost")


def test_kek_for_uses_per_domain_override(monkeypatch):
    monkeypatch.setenv("KEYSERVICE_ORIGINALS_KEK", "default-kek")
    monkeypatch.setenv("KEYSERVICE_ORIGINALS_KEK_BY_DOMAIN", '{"acme": "acme-kek"}')
    assert kek_for("acme") == "acme-kek"
    assert kek_for("other") == "default-kek"


def test_evict_drops_a_cached_entry(keyservice_session_factory):
    with keyservice_session_factory() as session:
        doc = _known(session)
        keys = DocumentKeys(_transit_for)
        minted = keys.mint(session, doc.id, "documents/a", doc.domain)
        session.commit()
        assert "documents/a" in keys._cache
        keys.evict(["documents/a"])
        assert "documents/a" not in keys._cache
        # still unwraps fine after eviction, from the row
        unwrapped = keys.unwrap(session, "documents/a")
    assert unwrapped.material == minted.material


def test_cache_stays_at_its_size_and_evicted_keys_are_unwrapped_again(
        keyservice_session_factory):
    class CountingTransit(FakeTransit):
        def __init__(self, kek):
            super().__init__(kek=kek)
            self.unwraps = 0

        def unwrap(self, ciphertext):
            self.unwraps += 1
            return super().unwrap(ciphertext)

    counters = {}

    def transit_for(name):
        if name not in counters:
            counters[name] = CountingTransit(hashlib.sha256(name.encode()).digest())
        return counters[name]

    with keyservice_session_factory() as session:
        doc = _known(session)
        keys = DocumentKeys(transit_for, cache_size=2, cache_ttl=1000)
        object_keys = []
        for i in range(3):
            object_key = f"documents/cache-{i}"
            keys.mint(session, doc.id, object_key, doc.domain)
            object_keys.append(object_key)
        session.commit()

        fresh = DocumentKeys(transit_for, cache_size=2, cache_ttl=1000)
        for object_key in object_keys:
            fresh.unwrap(session, object_key)
        assert len(fresh._cache) == 2

        name = kek_for(doc.domain)
        counters[name].unwraps = 0
        fresh.unwrap(session, object_keys[0])  # evicted earlier -> real unwrap again
        assert counters[name].unwraps == 1


def test_cache_entry_older_than_ttl_is_unwrapped_again(keyservice_session_factory):
    class CountingTransit(FakeTransit):
        def __init__(self, kek):
            super().__init__(kek=kek)
            self.unwraps = 0

        def unwrap(self, ciphertext):
            self.unwraps += 1
            return super().unwrap(ciphertext)

    transit = CountingTransit(hashlib.sha256(b"acme").digest())
    clock = {"t": 0.0}

    with keyservice_session_factory() as session:
        doc = _known(session)
        keys = DocumentKeys(lambda name: transit, cache_size=10, cache_ttl=5,
                            clock=lambda: clock["t"])
        keys.mint(session, doc.id, "documents/a", doc.domain)
        session.commit()

        keys.unwrap(session, "documents/a")  # cache hit, no unwrap
        assert transit.unwraps == 0

        clock["t"] += 10  # older than the ttl
        keys.unwrap(session, "documents/a")
    assert transit.unwraps == 1


# --- unwrap's classification (tasks.md: one test per case) ------------------

def _row_response(status_code: int) -> httpx.Response:
    return httpx.Response(status_code, request=httpx.Request("POST", "http://openbao/x"))


def test_connect_error_is_key_backend_unavailable(keyservice_session_factory):
    class ConnectErrorTransit:
        def wrap(self, plaintext):
            return b"wrapped"

        def unwrap(self, ciphertext):
            raise httpx.ConnectError("connection refused")

    with keyservice_session_factory() as session:
        doc = _known(session)
        keys = DocumentKeys(lambda name: ConnectErrorTransit())
        keys.mint(session, doc.id, "documents/a", doc.domain)
        session.commit()

        cold = DocumentKeys(lambda name: ConnectErrorTransit())
        with pytest.raises(KeyBackendUnavailable):
            cold.unwrap(session, "documents/a")


def test_timeout_is_key_backend_unavailable(keyservice_session_factory):
    class TimeoutTransit:
        def wrap(self, plaintext):
            return b"wrapped"

        def unwrap(self, ciphertext):
            raise httpx.TimeoutException("timed out")

    with keyservice_session_factory() as session:
        doc = _known(session)
        keys = DocumentKeys(lambda name: TimeoutTransit())
        keys.mint(session, doc.id, "documents/a", doc.domain)
        session.commit()

        cold = DocumentKeys(lambda name: TimeoutTransit())
        with pytest.raises(KeyBackendUnavailable):
            cold.unwrap(session, "documents/a")


def test_http_5xx_is_key_backend_unavailable(keyservice_session_factory):
    class ServerErrorTransit:
        def wrap(self, plaintext):
            return b"wrapped"

        def unwrap(self, ciphertext):
            resp = _row_response(503)
            raise httpx.HTTPStatusError("sealed", request=resp.request, response=resp)

    with keyservice_session_factory() as session:
        doc = _known(session)
        keys = DocumentKeys(lambda name: ServerErrorTransit())
        keys.mint(session, doc.id, "documents/a", doc.domain)
        session.commit()

        cold = DocumentKeys(lambda name: ServerErrorTransit())
        with pytest.raises(KeyBackendUnavailable):
            cold.unwrap(session, "documents/a")


def test_http_4xx_is_key_does_not_unwrap(keyservice_session_factory):
    class ClientErrorTransit:
        def wrap(self, plaintext):
            return b"wrapped"

        def unwrap(self, ciphertext):
            resp = _row_response(400)
            raise httpx.HTTPStatusError("bad request", request=resp.request, response=resp)

    with keyservice_session_factory() as session:
        doc = _known(session)
        keys = DocumentKeys(lambda name: ClientErrorTransit())
        keys.mint(session, doc.id, "documents/a", doc.domain)
        session.commit()

        cold = DocumentKeys(lambda name: ClientErrorTransit())
        with pytest.raises(KeyDoesNotUnwrap):
            cold.unwrap(session, "documents/a")


def test_invalid_tag_is_key_does_not_unwrap(keyservice_session_factory):
    with keyservice_session_factory() as session:
        doc = _known(session)
        keys = DocumentKeys(_transit_for)
        keys.mint(session, doc.id, "documents/a", doc.domain)
        session.commit()
        row = session.get(DocumentKeyRecord, "documents/a")
        row.wrapped_material = bytes([row.wrapped_material[0] ^ 0x01]) + row.wrapped_material[1:]
        session.flush()

        cold = DocumentKeys(_transit_for)  # cold cache, forces a real unwrap
        with pytest.raises(KeyDoesNotUnwrap):
            cold.unwrap(session, "documents/a")


def test_anything_else_propagates_as_is(keyservice_session_factory):
    class BoomTransit:
        def wrap(self, plaintext):
            return b"wrapped"

        def unwrap(self, ciphertext):
            raise RuntimeError("something unclassified")

    with keyservice_session_factory() as session:
        doc = _known(session)
        keys = DocumentKeys(lambda name: BoomTransit())
        keys.mint(session, doc.id, "documents/a", doc.domain)
        session.commit()

        cold = DocumentKeys(lambda name: BoomTransit())
        with pytest.raises(RuntimeError):
            cold.unwrap(session, "documents/a")
