# SPDX-License-Identifier: MIT
"""`scan_keys` takes only well-formed scan keys from the trail (review of #476):
a recovering `ocr` record without `old_object_key`, or with a value that is not a
content-addressed original key, is never locked, claimed or removed as a scan."""
from __future__ import annotations

from shred_setup import originals
from scan_setup import recover_document

from wordsworth import audit
from wordsworth.deletion_scans import scan_keys
from wordsworth.states import State


def _ocr_record(session, doc_id, payload):
    audit.append(session, document_id=doc_id, from_state=State.EXTRACTABLE.value,
                 to_state=State.EXTRACTABLE.value, step="ocr", payload=payload)


def test_only_well_formed_scan_keys_count(session, scanned_pdf):
    store = originals()
    doc_id, scan_key, _ocr_key = recover_document(session, store, scanned_pdf)
    _ocr_record(session, doc_id, {"note": "no key here"})
    _ocr_record(session, doc_id, {"old_object_key": None})
    _ocr_record(session, doc_id, {"old_object_key": "redacted/" + "0" * 64})
    _ocr_record(session, doc_id, {"old_object_key": "documents/../redacted/x"})
    session.flush()

    assert scan_keys(session, [doc_id]) == {scan_key}
