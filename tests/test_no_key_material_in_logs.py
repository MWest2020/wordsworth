# SPDX-License-Identifier: MIT
"""Task 5.1: clear DEK bytes never reach logs or exception messages, across
seal/open, mint/unwrap, and every failure path those two changes name."""
import base64
import logging
import os

import pytest

from wordsworth.document_keys import DocumentKeyRecord, DocumentKeys, OriginalsKeyUnavailable
from wordsworth.object_store import InMemoryObjectStore, SealedObjectError
from wordsworth.originals_envelope import open as envelope_open, seal
from wordsworth.originals_store import OriginalsStore
from wordsworth.pipeline import register
from wordsworth.transit import FakeTransit

DEK = os.urandom(32)


def _forms(material: bytes) -> list[bytes]:
    return [material, material.hex().encode(), base64.b64encode(material),
           base64.b64encode(material).decode().encode()]


def _assert_absent(material: bytes, *texts: str):
    haystacks = [t.encode("utf-8", "ignore") for t in texts]
    for form in _forms(material):
        for haystack in haystacks:
            assert form not in haystack


def test_seal_and_open_round_trip_leak_nothing(caplog):
    with caplog.at_level(logging.DEBUG):
        sealed = seal(DEK, "a" * 12, "documents/x", b"%PDF-1.4 content")
        envelope_open(DEK, "a" * 12, "documents/x", sealed)
    _assert_absent(DEK, caplog.text, sealed.decode("latin1"))


def _flip_last_byte(s: bytes) -> bytes:
    return s[:-1] + bytes([s[-1] ^ 1])


def _flip_first_ciphertext_byte(s: bytes) -> bytes:
    return s[:30] + bytes([s[30] ^ 1]) + s[31:]


@pytest.mark.parametrize("corrupt", [_flip_last_byte, _flip_first_ciphertext_byte])
def test_envelope_tamper_failures_leak_nothing(caplog, corrupt):
    sealed = seal(DEK, "a" * 12, "documents/x", b"%PDF-1.4 content")
    tampered = corrupt(sealed)
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(Exception) as exc_info:
            envelope_open(DEK, "a" * 12, "documents/x", tampered)
    _assert_absent(DEK, caplog.text, str(exc_info.value))


def test_envelope_wrong_key_id_failure_leaks_nothing(caplog):
    sealed = seal(DEK, "a" * 12, "documents/x", b"%PDF-1.4 content")
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(Exception) as exc_info:
            envelope_open(DEK, "b" * 12, "documents/x", sealed)
    _assert_absent(DEK, caplog.text, str(exc_info.value))


def test_envelope_wrong_object_key_failure_leaks_nothing(caplog):
    sealed = seal(DEK, "a" * 12, "documents/x", b"%PDF-1.4 content")
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(Exception) as exc_info:
            envelope_open(DEK, "a" * 12, "documents/y", sealed)
    _assert_absent(DEK, caplog.text, str(exc_info.value))


def _transit_for(name):
    import hashlib
    return FakeTransit(kek=hashlib.sha256(name.encode()).digest())


def test_mint_unwrap_round_trip_leaks_nothing(session, caplog):
    doc = register(session, "documents/log-a")
    session.flush()
    with caplog.at_level(logging.DEBUG):
        minted = DocumentKeys(_transit_for).mint(session, doc.id, doc.object_key, "_global")
        session.commit()
        unwrapped = DocumentKeys(_transit_for).unwrap(session, doc.object_key)
    _assert_absent(minted.material, caplog.text)
    _assert_absent(unwrapped.material, caplog.text)


def test_tampered_wrapped_material_failure_leaks_nothing(session, caplog):
    doc = register(session, "documents/log-b")
    session.flush()
    minted = DocumentKeys(_transit_for).mint(session, doc.id, doc.object_key, "_global")
    session.commit()
    row = session.get(DocumentKeyRecord, doc.object_key)
    row.wrapped_material = bytes([row.wrapped_material[0] ^ 1]) + row.wrapped_material[1:]
    session.flush()
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(OriginalsKeyUnavailable) as exc_info:
            DocumentKeys(_transit_for).unwrap(session, doc.object_key)
    _assert_absent(minted.material, caplog.text, str(exc_info.value))


def test_wrong_kek_failure_leaks_nothing(session, caplog):
    doc = register(session, "documents/log-c")
    session.flush()
    minted = DocumentKeys(_transit_for).mint(session, doc.id, doc.object_key, "_global")
    session.commit()
    row = session.get(DocumentKeyRecord, doc.object_key)
    row.kek_ref = "a-different-kek"
    session.flush()
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(OriginalsKeyUnavailable) as exc_info:
            DocumentKeys(_transit_for).unwrap(session, doc.object_key)
    _assert_absent(minted.material, caplog.text, str(exc_info.value))


def test_raising_transit_failure_leaks_nothing(session, caplog):
    doc = register(session, "documents/log-d")
    session.flush()

    class BoomTransit:
        def wrap(self, plaintext):
            return b"wrapped"

        def unwrap(self, ciphertext):
            raise RuntimeError("transit unavailable")

    with caplog.at_level(logging.DEBUG):
        minted = DocumentKeys(lambda name: BoomTransit()).mint(
            session, doc.id, doc.object_key, "_global")
        session.commit()
        with pytest.raises(OriginalsKeyUnavailable) as exc_info:
            DocumentKeys(lambda name: BoomTransit()).unwrap(session, doc.object_key)
    _assert_absent(minted.material, caplog.text, str(exc_info.value))


def test_put_original_and_downgrade_failures_leak_nothing(session, caplog):
    store = OriginalsStore(InMemoryObjectStore(), DocumentKeys(_transit_for))
    doc = register(session, "documents/log-e")
    session.flush()
    with caplog.at_level(logging.DEBUG):
        store.put_original(session, doc.id, doc.object_key, b"%PDF-1.4 hello")
        session.commit()
        material_proxy = DocumentKeys(_transit_for).unwrap(session, doc.object_key).material
        store.objects.put(doc.object_key, b"%PDF-1.4 downgraded")
        with pytest.raises(SealedObjectError) as exc_info:
            store.put_original(session, doc.id, doc.object_key, b"new")
    _assert_absent(material_proxy, caplog.text, str(exc_info.value))
