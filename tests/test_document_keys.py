# SPDX-License-Identifier: MIT
"""The `document_keys` table and `DocumentKeys` store (task 2):  mint/unwrap,
the bounded+TTL cache, KEK-per-domain, and that `db.py` carries the table even
when nothing imports `document_keys` directly (task 2.4)."""
import hashlib

import pytest

from wordsworth.document_keys import DocumentKeyRecord, DocumentKeys, OriginalsKeyUnavailable, kek_name_for
from wordsworth.pipeline import register
from wordsworth.transit import FakeTransit


def _transit_for(name: str) -> FakeTransit:
    """The name-keyed factory design.md prescribes for tests: a key wrapped
    under one name really fails to unwrap under another."""
    return FakeTransit(kek=hashlib.sha256(name.encode()).digest())


def _doc(session, key="documents/a"):
    doc = register(session, key)
    session.flush()
    return doc


# --- import surface ---------------------------------------------------------

def test_errors_and_name_function_import_from_document_keys():
    from wordsworth.document_keys import OriginalsKeyUnavailable as E  # noqa: F401
    from wordsworth.document_keys import kek_name_for as f  # noqa: F401


# --- mint / unwrap round trip -----------------------------------------------

def test_mint_then_unwrap_round_trips_through_named_transit(session):
    doc = _doc(session)
    keys = DocumentKeys(_transit_for)
    minted = keys.mint(session, doc.id, doc.object_key, "acme")
    session.commit()

    fresh = DocumentKeys(_transit_for)  # cold cache
    unwrapped = fresh.unwrap(session, doc.object_key)
    assert unwrapped.key_id == minted.key_id
    assert unwrapped.material == minted.material


def test_row_never_holds_the_clear_dek(session):
    doc = _doc(session)
    minted = DocumentKeys(_transit_for).mint(session, doc.id, doc.object_key, "acme")
    session.commit()
    row = session.get(DocumentKeyRecord, doc.object_key)
    assert row.wrapped_material != minted.material
    assert minted.material not in row.wrapped_material


def test_unwrap_with_no_row_raises_key_unavailable(session):
    with pytest.raises(OriginalsKeyUnavailable):
        DocumentKeys(_transit_for).unwrap(session, "documents/ghost")


# --- negative tests: tampered material, wrong KEK, raising transit ---------

def test_tampered_wrapped_material_fails_closed_with_no_key_material(session):
    doc = _doc(session)
    keys = DocumentKeys(_transit_for)
    minted = keys.mint(session, doc.id, doc.object_key, "acme")
    session.commit()
    row = session.get(DocumentKeyRecord, doc.object_key)
    row.wrapped_material = bytes([row.wrapped_material[0] ^ 0x01]) + row.wrapped_material[1:]
    session.flush()

    fresh = DocumentKeys(_transit_for)  # cold cache, forces a real unwrap
    with pytest.raises(OriginalsKeyUnavailable) as exc_info:
        fresh.unwrap(session, doc.object_key)
    message = str(exc_info.value)
    assert minted.material.hex() not in message
    import base64
    assert base64.b64encode(minted.material).decode() not in message


def test_row_naming_another_kek_than_the_one_that_wrapped_it_fails_closed(session):
    doc = _doc(session)
    keys = DocumentKeys(_transit_for)
    keys.mint(session, doc.id, doc.object_key, "acme")
    session.commit()
    row = session.get(DocumentKeyRecord, doc.object_key)
    row.kek_ref = "a-different-kek"
    session.flush()

    fresh = DocumentKeys(_transit_for)  # cold cache
    with pytest.raises(OriginalsKeyUnavailable):
        fresh.unwrap(session, doc.object_key)


def test_a_transit_that_raises_fails_closed_on_unwrap(session):
    doc = _doc(session)
    DocumentKeys(_transit_for).mint(session, doc.id, doc.object_key, "acme")
    session.commit()

    class BoomTransit:
        def wrap(self, plaintext):
            return b"wrapped"

        def unwrap(self, ciphertext):
            raise RuntimeError("transit unavailable")

    boom = DocumentKeys(lambda name: BoomTransit())
    with pytest.raises(OriginalsKeyUnavailable):
        boom.unwrap(session, doc.object_key)


def test_a_transit_that_raises_fails_closed_on_mint_before_any_write(session):
    doc = _doc(session)

    class BoomTransit:
        def wrap(self, plaintext):
            raise RuntimeError("transit unavailable")

        def unwrap(self, ciphertext):
            raise RuntimeError("transit unavailable")

    boom = DocumentKeys(lambda name: BoomTransit())
    with pytest.raises(OriginalsKeyUnavailable):
        boom.mint(session, doc.id, doc.object_key, "acme")
    assert session.get(DocumentKeyRecord, doc.object_key) is None


# --- cache: bounded size and TTL (task 2.2) ---------------------------------

def test_cache_stays_at_its_size_and_evicted_keys_are_unwrapped_again(session):
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

    keys = DocumentKeys(transit_for, cache_size=2, cache_ttl=1000)
    docs = []
    for i in range(3):
        doc = _doc(session, key=f"documents/cache-{i}")
        keys.mint(session, doc.id, doc.object_key, "acme")
        docs.append(doc)
    session.commit()

    # Minting warms the cache already; force a fresh unwrap count by cold cache.
    fresh = DocumentKeys(transit_for, cache_size=2, cache_ttl=1000)
    for doc in docs:
        fresh.unwrap(session, doc.object_key)
    assert len(fresh._cache) == 2

    from wordsworth.document_keys import kek_name_for

    name = kek_name_for("acme")
    counters[name].unwraps = 0
    fresh.unwrap(session, docs[0].object_key)  # evicted earlier -> real unwrap again
    assert counters[name].unwraps == 1


def test_cache_entry_older_than_ttl_is_unwrapped_again(session):
    doc = _doc(session)

    class CountingTransit(FakeTransit):
        def __init__(self, kek):
            super().__init__(kek=kek)
            self.unwraps = 0

        def unwrap(self, ciphertext):
            self.unwraps += 1
            return super().unwrap(ciphertext)

    transit = CountingTransit(hashlib.sha256(b"acme").digest())
    clock = {"t": 0.0}
    keys = DocumentKeys(lambda name: transit, cache_size=10, cache_ttl=5,
                        clock=lambda: clock["t"])
    keys.mint(session, doc.id, doc.object_key, "acme")
    session.commit()

    keys.unwrap(session, doc.object_key)  # cache hit, no unwrap
    assert transit.unwraps == 0

    clock["t"] += 10  # older than the ttl
    keys.unwrap(session, doc.object_key)
    assert transit.unwraps == 1


# --- KEK per domain (task 2.3) ----------------------------------------------

def test_kek_name_for_uses_per_domain_override(monkeypatch):
    monkeypatch.setenv("WORDSWORTH_ORIGINALS_KEK", "default-kek")
    monkeypatch.setenv("WORDSWORTH_ORIGINALS_KEK_BY_DOMAIN", '{"acme": "acme-kek"}')
    assert kek_name_for("acme") == "acme-kek"
    assert kek_name_for("other") == "default-kek"


def test_changing_the_kek_setting_between_mint_and_unwrap_does_not_move_old_rows(
        session, monkeypatch):
    doc = _doc(session)
    monkeypatch.setenv("WORDSWORTH_ORIGINALS_KEK_BY_DOMAIN", '{"acme": "kek-a"}')
    keys = DocumentKeys(_transit_for)
    minted = keys.mint(session, doc.id, doc.object_key, "acme")
    session.commit()

    monkeypatch.setenv("WORDSWORTH_ORIGINALS_KEK_BY_DOMAIN", '{"acme": "kek-b"}')
    fresh = DocumentKeys(_transit_for)  # cold cache, re-reads the row's own kek_ref
    unwrapped = fresh.unwrap(session, doc.object_key)
    assert unwrapped.material == minted.material


# --- db.py wires the table onto Base.metadata (task 2.4) -------------------

def test_init_schema_creates_document_keys_without_importing_it_directly(database_url):
    import os
    import subprocess
    import sys

    code = (
        "import sys\n"
        "assert 'wordsworth.document_keys' not in sys.modules\n"
        "from wordsworth.db import init_schema, make_engine\n"
        "assert 'wordsworth.document_keys' in sys.modules, 'db.py must import it'\n"
        "import os\n"
        "engine = make_engine(os.environ['WORDSWORTH_TEST_DATABASE_URL'])\n"
        "init_schema(engine)\n"
        "from sqlalchemy import inspect\n"
        "insp = inspect(engine)\n"
        "assert 'document_keys' in insp.get_table_names()\n"
        "idx_cols = [ix['column_names'] for ix in insp.get_indexes('document_keys')]\n"
        "assert any('document_id' in cols for cols in idx_cols), idx_cols\n"
    )
    env = dict(os.environ)
    env["WORDSWORTH_TEST_DATABASE_URL"] = database_url
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env)
    assert result.returncode == 0, result.stdout + result.stderr
