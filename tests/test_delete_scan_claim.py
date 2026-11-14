# SPDX-License-Identifier: MIT
"""`delete-removes-original-scan` task 1: a document claims an object key not
only through its row, but through a recovering `ocr` record naming it as the
scan -- and the key candidates widen with that claim (A is a recovered
document with scan S, C a superseded copy whose `object_key` is S, N a later
ingest of S's bytes -- as in `tasks.md`)."""
from __future__ import annotations

from shred_setup import key_row, originals
from scan_setup import recover_now

from wordsworth.deletion import delete_document
from wordsworth.deletion_scans import scan_keys
from wordsworth.pipeline import ingest, register
from wordsworth.search_index import InMemoryIndex
from wordsworth.supersession import supersede


def test_scan_keys_reads_back_the_recovering_ocr_record(session, scanned_pdf):
    store = originals()
    doc = ingest(session, store, scanned_pdf)
    session.commit()
    scan_key = doc.object_key
    ocr_key = recover_now(session, store, doc.id)

    assert scan_keys(session, [doc.id]) == {scan_key}
    assert ocr_key not in scan_keys(session, [doc.id])


def test_scan_keys_of_a_document_never_recovered_is_empty(session):
    doc = register(session, "documents/" + "ab" * 32)
    session.commit()

    assert scan_keys(session, [doc.id]) == set()


def test_deleting_a_copy_of_the_scan_leaves_it_while_the_survivor_is_recovered(
        legacy_copies, scanned_pdf):
    """C was retired while A still had S; A was recovered afterwards. Today's
    rule (a row pointing at the key) would say nothing claims S any more --
    the new clause (A's `ocr` record names S) says A still does."""
    store = originals()
    with legacy_copies() as s:
        survivor = ingest(s, store, scanned_pdf)
        s.commit()
        scan_key = survivor.object_key
        copy = register(s, scan_key)
        s.commit()
        supersede(s, copy.id, survivor.id, actor="t")
        s.commit()

        ocr_key = recover_now(s, store, survivor.id)
        assert ocr_key != scan_key

        counts = delete_document(s, copy.id, store, InMemoryIndex(), actor="t")
        s.commit()

        assert counts.object == 0 and counts.keys_destroyed == 0
        assert store.objects.exists(scan_key)
        assert key_row(s, scan_key) is not None


def test_deleting_a_re_ingest_of_the_scan_leaves_it_while_the_recovered_document_is_live(
        session_factory, scanned_pdf):
    """N re-ingests S's bytes after A moved off S; `put_original` moves S's
    key row to N. Deleting N while A is live must not take S (or its key)
    from under A -- today it would, since N's row no longer shares A's id or
    object key."""
    store = originals()
    with session_factory() as s:
        a = ingest(s, store, scanned_pdf)
        s.commit()
        scan_key = a.object_key
        recover_now(s, store, a.id)

        n = ingest(s, store, scanned_pdf)
        s.commit()
        assert n.object_key == scan_key
        assert key_row(s, scan_key).document_id == n.id

        counts = delete_document(s, n.id, store, InMemoryIndex(), actor="t")
        s.commit()

        assert counts.object == 0 and counts.keys_destroyed == 0
        assert store.objects.exists(scan_key)
        assert key_row(s, scan_key) is not None


def test_candidate_rows_reaches_a_key_row_the_re_ingest_moved(session_factory, scanned_pdf):
    """The sequence that defeats crypto-shred without the new clause: A
    recovered with scan S; S's bytes ingested again as N (key row moves to
    N); N deleted while A lives (S and its key stay, by the claim); A deleted.
    Without `object_key IN scan_keys(document_id)` in `_candidate_rows`, S's
    key row (`document_id = N`) is not a candidate of A's deletion and
    survives; with it, both S and the row go."""
    store = originals()
    with session_factory() as s:
        a = ingest(s, store, scanned_pdf)
        s.commit()
        scan_key = a.object_key
        recover_now(s, store, a.id)

        n = ingest(s, store, scanned_pdf)
        s.commit()
        assert key_row(s, scan_key).document_id == n.id

        delete_document(s, n.id, store, InMemoryIndex(), actor="t")
        s.commit()
        assert store.objects.exists(scan_key) and key_row(s, scan_key) is not None

        counts = delete_document(s, a.id, store, InMemoryIndex(), actor="t")
        s.commit()

        assert counts.original_scan == 1 and counts.keys_destroyed == 2

    assert not store.objects.exists(scan_key)
    with session_factory() as s:
        assert key_row(s, scan_key) is None
