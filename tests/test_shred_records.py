# SPDX-License-Identifier: MIT
"""`originals-crypto-shred` task 2: the records. The `deleted` record counts
the destroyed keys and carries no key material; a rerun over an already
deleted document that still has a key destroys it and appends one
`destroy-key` record."""
from __future__ import annotations

import base64
import json
from datetime import datetime, timezone

from sqlalchemy import func, select

from shred_setup import KEY, CountingTransit, key_row, keys_over, originals, sealed
from wordsworth.audit import verify_chain
from wordsworth.deletion import delete_document
from wordsworth.document_keys import DocumentKeyRecord
from wordsworth.models import AuditRecord, BoxMap
from wordsworth.pdf_redaction import redacted_cache_key
from wordsworth.pipeline import register
from wordsworth.search_index import InMemoryIndex


def _records(session, doc_id, step=None):
    q = select(AuditRecord).where(AuditRecord.document_id == doc_id)
    if step:
        q = q.where(AuditRecord.step == step)
    return session.execute(q.order_by(AuditRecord.seq)).scalars().all()


def _material_strings(*blobs: bytes) -> list[str]:
    return [form for b in blobs
            for form in (b.hex(), base64.b64encode(b).decode())]


def test_the_records_carry_the_count_and_no_key_material(session):
    transit = CountingTransit()
    store, index = originals(transit), InMemoryIndex()
    doc_id = sealed(session, store)
    session.commit()
    wrapped = key_row(session).wrapped_material
    clear = keys_over(transit).unwrap(session, KEY).material

    delete_document(session, doc_id, store, index, actor="t")
    session.commit()
    _put_row_back(session, doc_id)
    delete_document(session, doc_id, store, index, actor="t")
    session.commit()

    for rec in _records(session, doc_id):
        dumped = json.dumps(rec.payload)
        for form in _material_strings(wrapped, clear):
            assert form not in dumped
    assert _records(session, doc_id, "delete")[0].payload["keys_destroyed"] == 1


def _put_row_back(session, doc_id):
    """A document deleted before this change: its key row was left behind."""
    now = datetime.now(timezone.utc)
    session.add(DocumentKeyRecord(
        object_key=KEY, document_id=doc_id, key_id="0123456789ab",
        kek_ref="wordsworth", wrapped_material=b"wrapped-left-behind",
        created_at=now, sealed_at=now))
    session.commit()


def test_a_rerun_over_a_deleted_document_destroys_a_left_key_and_records_it(session):
    store, index = originals(), InMemoryIndex()
    doc = register(session, KEY)
    session.commit()
    delete_document(session, doc.id, store, index, actor="t")
    session.commit()
    _put_row_back(session, doc.id)
    count = lambda: session.execute(  # noqa: E731
        select(func.count()).select_from(AuditRecord)
        .where(AuditRecord.document_id == doc.id)).scalar_one()
    before = count()

    counts = delete_document(session, doc.id, store, index, actor="operator")
    session.commit()

    assert counts.keys_destroyed == 1
    assert key_row(session) is None
    assert count() == before + 1
    rec = _records(session, doc.id)[-1]
    assert (rec.from_state, rec.to_state, rec.step) == ("deleted", "deleted", "destroy-key")
    assert rec.payload == {"actor": "operator", "keys_destroyed": 1}
    ok, bad = verify_chain(session)
    assert ok and bad is None

    again = delete_document(session, doc.id, store, index, actor="operator")
    session.commit()
    assert again.keys_destroyed == 0
    assert count() == before + 1  # nothing to destroy, nothing appended


def test_a_rerun_that_finds_a_key_and_a_render_writes_one_record_for_each(session):
    """Two records, not one: `remove-renders` (#453) and `destroy-key` keep
    their own steps and payloads, in the same transaction."""
    store, index = originals(), InMemoryIndex()
    doc = register(session, KEY)
    session.commit()
    delete_document(session, doc.id, store, index, actor="t")
    session.commit()
    _put_row_back(session, doc.id)
    session.add(BoxMap(document_id=doc.id, boxmap_hash="h" * 64,
                       lists_hash=None, boxes=[]))
    store.objects.put(redacted_cache_key(doc.id, 1, "h" * 64), b"%PDF-1.4")
    session.commit()
    seen = len(_records(session, doc.id))

    counts = delete_document(session, doc.id, store, index, actor="op")
    session.commit()

    new = _records(session, doc.id)[seen:]
    assert [(r.step, r.from_state, r.to_state) for r in new] == [
        ("remove-renders", "deleted", "deleted"), ("destroy-key", "deleted", "deleted")]
    assert new[0].payload == {"actor": "op", "renders_removed": 1, "box_maps_removed": 1,
                              "summaries_removed": 0}
    assert new[1].payload == {"actor": "op", "keys_destroyed": 1}
    assert (counts.keys_destroyed, counts.renders_removed) == (1, 1)
    assert verify_chain(session) == (True, None)
