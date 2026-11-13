# SPDX-License-Identifier: MIT
"""Seed the demo dossier through the pipeline itself: ingest, process, delete,
supersede -- the functions production calls, so every row and audit record is
one the real code wrote, never one inserted by hand."""
from __future__ import annotations

from wordsworth.deletion import delete_document
from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.models import Document
from wordsworth.pipeline import ingest, process
from wordsworth.states import State
from wordsworth.supersession import supersede

from demo import corpus

ACTOR = "demo-seed"
# Which letters end up deleted, and which one also arrived as a scan. Fixed, so
# the walk in the how-to can name them.
DELETED = ("demo-029", "demo-030")
SCANNED = "demo-001"


def seed(stand_ins) -> dict:
    """Ingest and process every letter into the demo dossier, then delete two
    and supersede a scanned copy of a third. Returns document ids by kenmerk."""
    docs = corpus.documents()
    ids = {}
    sf = stand_ins.session_factory
    for d in docs:
        ids[d.doc_id] = _ingest_one(stand_ins, corpus.render(d), corpus.filename(d))
    survivor = next(d for d in docs if d.doc_id == SCANNED)
    scan_id = _ingest_one(stand_ins, corpus.render_scan(survivor),
                          f"{SCANNED}-scan.pdf", expect=State.UNPROCESSABLE_OCR)
    with sf() as s:
        for kenmerk in DELETED:
            delete_document(s, ids[kenmerk], stand_ins.store, stand_ins.index,
                            actor=ACTOR)
        # The OCR-recovery shape (recovery.py): a scan whose readable version is
        # an object another document already holds becomes a copy of that one.
        survivor_key = s.get(Document, ids[SCANNED]).object_key
        supersede(s, scan_id, ids[SCANNED], actor=ACTOR, index=stand_ins.index,
                  as_object=survivor_key)
        s.commit()
    return {"ids": ids, "scan": scan_id}


def _ingest_one(stand_ins, pdf: bytes, filename: str, expect=State.INDEXED):
    with stand_ins.session_factory() as s:
        doc = ingest(s, stand_ins.store, pdf, filename=filename,
                     dossier=corpus.DOSSIER)
        s.commit()
        state = process(s, doc.id, stand_ins.store,
                        anonymizer=stand_ins.anonymizer(s),
                        search_index=stand_ins.index, embedder=stand_ins.embedder,
                        key_provider=stand_ins.key_provider,
                        mapping_store=PostgresMappingStore(s))
        s.commit()
        if state != expect:
            # A seed that ends anywhere else is a demo that lies about itself.
            raise RuntimeError(f"{filename}: ended in {state.value}, "
                               f"expected {expect.value}")
        return doc.id
