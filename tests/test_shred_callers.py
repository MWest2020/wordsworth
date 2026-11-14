# SPDX-License-Identifier: MIT
"""`originals-crypto-shred` task 3: every caller shreds -- the API (which
also evicts its cache), `wordsworth-delete` with a plain object store and no
key service, and a dossier deletion -- and the counts reach every report,
dry run and real (a dossier also sums `renders_removed` and
`box_maps_removed`, #453)."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from shred_setup import KEY, key_row, originals, sealed
from wordsworth import dossiers
from wordsworth.api import create_app
from wordsworth.delete_cli import main
from wordsworth.dossier_deletion import delete_dossier
from wordsworth.models import BoxMap
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.pdf_redaction import redacted_cache_key
from wordsworth.search_index import InMemoryIndex

ISSUER = {"api_keys": {"k-issuer": "issuer-caller"},
          "grant_issuer_labels": ["issuer-caller"]}
HEADERS = {"X-API-Key": "k-issuer"}
A, B, SHARED = ("documents/" + c * 64 for c in "abc")


def _client(session_factory, store):
    return TestClient(create_app(session_factory=session_factory, store=store,
                                 search_index=InMemoryIndex(), **ISSUER))


def _cli(session_factory, store, *args):
    return main([*args, "--actor", "operator"], session_factory=session_factory,
                store=store, index=InMemoryIndex(), issuer_labels=["operator"])


def test_the_api_destroys_the_key_and_evicts_its_cache(session_factory):
    store = originals()
    with session_factory() as s:
        doc_id = sealed(s, store)
        s.commit()
        store.get_original(s, KEY)  # warm the API process's cache
    r = _client(session_factory, store).delete(f"/documents/{doc_id}", headers=HEADERS)
    assert r.status_code == 200 and r.json()["keys_destroyed"] == 1
    assert KEY not in store.keys._cache
    with session_factory() as s:
        assert key_row(s) is None


def test_the_cli_with_a_plain_store_and_no_key_service_shreds(session_factory, capsys):
    sealing = originals()
    with session_factory() as s:
        doc_id = sealed(s, sealing)
        s.commit()
    plain = sealing.objects  # what `wordsworth-delete` builds: no keys at all
    assert isinstance(plain, InMemoryObjectStore)

    assert _cli(session_factory, plain, str(doc_id), "--dry-run") == 0
    dry = json.loads(capsys.readouterr().out)["results"][0]
    with session_factory() as s:
        assert dry["keys_destroyed"] == 1 and key_row(s) is not None

    assert _cli(session_factory, plain, str(doc_id)) == 0
    real = json.loads(capsys.readouterr().out)["results"][0]
    assert real["keys_destroyed"] == dry["keys_destroyed"]
    with session_factory() as s:
        assert key_row(s) is None


def test_a_dossier_deletion_passes_keys_on(session_factory):
    store = originals()
    with session_factory() as s:
        doc_id = sealed(s, store)
        dossier = dossiers.ensure(s, "zaak")
        dossiers.add(s, dossier.id, doc_id, actor="t")
        s.commit()
        store.get_original(s, KEY)
        report = delete_dossier(s, dossier.id, store, InMemoryIndex(), actor="t",
                                keys=store.keys)
        s.commit()
        assert report.keys_destroyed == 1
        assert KEY not in store.keys._cache
        assert key_row(s) is None


def _dossier_of_three(session_factory):
    """Two sealed documents only in this dossier, one shared with another,
    each with a cached render and a box map: a deletion deletes two and
    releases one, so it destroys two keys and removes two of each."""
    store = originals()
    with session_factory() as s:
        mine, theirs = dossiers.ensure(s, "zaak-a"), dossiers.ensure(s, "zaak-b")
        for key in (A, B, SHARED):
            doc_id = sealed(s, store, key=key, data=key.encode())
            dossiers.add(s, mine.id, doc_id, actor="t")
            s.add(BoxMap(document_id=doc_id, boxmap_hash="h" * 64,
                         lists_hash=None, boxes=[]))
            store.objects.put(redacted_cache_key(doc_id, 1, "h" * 64), b"%PDF-1.4")
        shared_id = key_row(s, SHARED).document_id
        dossiers.add(s, theirs.id, shared_id, actor="t")
        s.commit()
        return store, mine.id


def _sums(report: dict) -> tuple[int, int, int]:
    return (report["keys_destroyed"], report["renders_removed"],
            report["box_maps_removed"])


def _rows_left(session_factory):
    with session_factory() as s:
        return {k for k in (A, B, SHARED) if key_row(s, k) is not None}


def test_a_dossier_reports_the_sum_in_as_dict(session_factory):
    store, dossier_id = _dossier_of_three(session_factory)
    with session_factory() as s:
        dry = delete_dossier(s, dossier_id, store, InMemoryIndex(), actor="t",
                             dry_run=True)
        s.rollback()
    assert _sums(dry.as_dict()) == (2, 2, 2)
    assert _rows_left(session_factory) == {A, B, SHARED}
    with session_factory() as s:
        real = delete_dossier(s, dossier_id, store, InMemoryIndex(), actor="t")
        s.commit()
    assert _sums(real.as_dict()) == (2, 2, 2)
    assert _rows_left(session_factory) == {SHARED}


def test_a_dossier_reports_the_sum_in_the_api_answer(session_factory):
    store, dossier_id = _dossier_of_three(session_factory)
    r = _client(session_factory, store).delete(f"/dossiers/{dossier_id}",
                                               headers=HEADERS)
    assert r.status_code == 200 and _sums(r.json()) == (2, 2, 2)
    assert _rows_left(session_factory) == {SHARED}


def test_a_dossier_reports_the_sum_in_the_cli_output(session_factory, capsys):
    store, dossier_id = _dossier_of_three(session_factory)
    plain = store.objects
    assert _cli(session_factory, plain, "--dossier", str(dossier_id), "--dry-run") == 0
    dry = json.loads(capsys.readouterr().out)["results"][0]
    assert _sums(dry) == (2, 2, 2)
    assert _rows_left(session_factory) == {A, B, SHARED}

    assert _cli(session_factory, plain, "--dossier", str(dossier_id)) == 0
    real = json.loads(capsys.readouterr().out)["results"][0]
    assert _sums(real) == (2, 2, 2)
    assert _rows_left(session_factory) == {SHARED}
