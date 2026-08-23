"""API-key auth on the reveal path — DB-backed (CI). The authenticated caller is
recorded in the deanonymize audit, distinct from the grant recipient."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from wordsworth.api import create_app
from wordsworth.grants import InMemoryGrantStore
from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.models import AuditRecord
from wordsworth.pipeline import ingest, process
from wordsworth.pseudonymizer import Pseudonymizer

PII_EMAIL = "jan.jansen@haarlem.nl"


def test_reveal_requires_key_and_records_caller(
        session_factory, mem_store, mem_index, fake_embedder, born_digital_pii_pdf):
    kp = InMemoryKeyProvider()
    with session_factory() as s:
        doc = ingest(s, mem_store, born_digital_pii_pdf)
        s.commit()
        process(s, doc.id, mem_store,
                anonymizer=Pseudonymizer(kp, PostgresMappingStore(s)),
                search_index=mem_index, embedder=fake_embedder)
        s.commit()
        did = doc.id
    gs = InMemoryGrantStore()
    grant = gs.issue("agent-x", ["EMAIL"], actor="mark", document_id=did)
    c = TestClient(create_app(session_factory=session_factory, key_provider=kp,
                              grant_store=gs, api_keys={"sk_v": "alice"},
                              rate_limiters={}))

    # No key → 401 (auth enforced when configured)
    assert c.post(f"/documents/{did}/reveal",
                  json={"grant_id": grant.grant_id}).status_code == 401

    # Valid key → 200, and the audit records the authenticated caller AND the
    # grant recipient, with no clear PII.
    r = c.post(f"/documents/{did}/reveal", json={"grant_id": grant.grant_id},
               headers={"X-API-Key": "sk_v"})
    assert r.status_code == 200
    with session_factory() as s:
        rec = s.execute(
            select(AuditRecord).where(AuditRecord.step == "deanonymize")
        ).scalar_one()
        assert rec.payload["caller"] == "alice"        # authenticated caller
        assert rec.payload["actor"] == "agent-x"       # grant recipient (unchanged)
        assert PII_EMAIL not in str(rec.payload)
