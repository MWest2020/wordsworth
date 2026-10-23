"""ingest-records-source: provenance travels with the document.

Design.md tests 1 and 2 (the seam the reviewer requires): fields posted at
ingest reach both the document row and the register step of the audit chain,
and omitting them leaves today's result unchanged except for the sha256
wordsworth now always records itself.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import select

from wordsworth.keys import DEFAULT_DOMAIN
from wordsworth.models import AuditRecord, Document
from wordsworth.pipeline import ingest


def _register_payload(session, document_id):
    return session.execute(
        select(AuditRecord.payload)
        .where(AuditRecord.document_id == document_id, AuditRecord.step == "register")
    ).scalar_one()


def test_fields_reach_the_document_and_the_audit_record(
    session, born_digital_pdf, mem_store,
):
    fetched_at = datetime(2026, 10, 20, 9, 30, tzinfo=timezone.utc)
    doc = ingest(session, mem_store, born_digital_pdf,
                source_url="https://gooisemeren.nl/publicatie.pdf",
                fetched_at=fetched_at)
    session.commit()

    digest = hashlib.sha256(born_digital_pdf).hexdigest()
    stored = session.get(Document, doc.id)
    assert stored.source_url == "https://gooisemeren.nl/publicatie.pdf"
    assert stored.fetched_at == fetched_at
    assert stored.source_sha256 == digest

    payload = _register_payload(session, doc.id)
    assert payload["source_url"] == "https://gooisemeren.nl/publicatie.pdf"
    assert payload["fetched_at"] == fetched_at.isoformat()
    assert payload["source_sha256"] == digest


def test_omitting_both_fields_leaves_ingest_unchanged(session, born_digital_pdf, mem_store):
    doc = ingest(session, mem_store, born_digital_pdf)
    session.commit()

    digest = hashlib.sha256(born_digital_pdf).hexdigest()
    stored = session.get(Document, doc.id)
    assert stored.source_url is None
    assert stored.fetched_at is None
    assert stored.source_sha256 == digest  # always recorded, omission or not

    payload = _register_payload(session, doc.id)
    assert payload == {"domain": DEFAULT_DOMAIN, "source_sha256": digest}
    assert "source_url" not in payload and "fetched_at" not in payload
