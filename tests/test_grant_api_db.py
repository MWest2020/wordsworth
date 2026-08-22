"""Grant API enforcement against the real reveal path (add-grant-api).

DB-backed: issuing then revoking a grant over HTTP must actually gate the reveal
endpoint. Runs in CI against Postgres; skips locally without a DB."""
from __future__ import annotations

from fastapi.testclient import TestClient

from wordsworth.api import create_app
from wordsworth.grants import InMemoryGrantStore
from wordsworth.key_audit import JsonlKeyLifecycleAudit
from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.pipeline import ingest, process
from wordsworth.pseudonymizer import Pseudonymizer


def test_issue_then_revoke_gates_reveal(session_factory, mem_store, mem_index,
                                        fake_embedder, born_digital_pii_pdf, tmp_path):
    kp = InMemoryKeyProvider()
    with session_factory() as s:
        doc = ingest(s, mem_store, born_digital_pii_pdf)
        s.commit()
        process(s, doc.id, mem_store,
                anonymizer=Pseudonymizer(kp, PostgresMappingStore(s)),
                search_index=mem_index, embedder=fake_embedder)
        s.commit()
        doc_id = doc.id

    gs = InMemoryGrantStore()
    c = TestClient(create_app(
        session_factory=session_factory, key_provider=kp, grant_store=gs,
        key_audit=JsonlKeyLifecycleAudit(tmp_path / "ka.jsonl")))

    # issue over HTTP
    r = c.post("/grants", json={"recipient": "auditor", "allowed_types": ["EMAIL"],
                                "document_id": str(doc_id)})
    assert r.status_code == 201
    gid = r.json()["grant_id"]

    # reveal works while the grant is active
    assert c.post(f"/documents/{doc_id}/reveal",
                  json={"grant_id": gid}).status_code == 200

    # revoke over HTTP
    assert c.post(f"/grants/{gid}/revoke").json()["status"] == "revoked"

    # reveal is now forbidden
    assert c.post(f"/documents/{doc_id}/reveal",
                  json={"grant_id": gid}).status_code == 403
