"""add-pii-categories-and-ppl: PPL shorthand on grants, legal-basis grouping on
reveal, categories in the reveal audit, category counts in metadata."""
from fastapi.testclient import TestClient
from sqlalchemy import select

from wordsworth.api import create_app
from wordsworth.client import main as cli_main
from wordsworth.grants import InMemoryGrantStore
from wordsworth.key_audit import JsonlKeyLifecycleAudit
from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.models import AuditRecord
from wordsworth.pii_categories import types_for_ppl
from wordsworth.pipeline import ingest, process
from wordsworth.pseudonymizer import Pseudonymizer

PII_BSN = "123456782"


def _app(session_factory, tmp_path, kp=None, gs=None):
    return TestClient(create_app(session_factory=session_factory,
                                 key_provider=kp or InMemoryKeyProvider(),
                                 grant_store=gs or InMemoryGrantStore(),
                                 key_audit=JsonlKeyLifecycleAudit(tmp_path / "k.jsonl")))


def test_issue_by_ppl_expands_to_types(session_factory, tmp_path):
    c = _app(session_factory, tmp_path)
    r = c.post("/grants", json={"recipient": "r", "ppl": 1})
    assert r.status_code == 201, r.text
    body = r.json()
    assert set(body["allowed_types"]) == types_for_ppl(1)
    assert body["ppl"] == 1
    assert "GEZONDHEID" not in body["allowed_types"]


def test_issue_ppl_zero_grants_nothing(session_factory, tmp_path):
    r = _app(session_factory, tmp_path).post("/grants", json={"recipient": "r", "ppl": 0})
    assert r.status_code == 201 and r.json()["allowed_types"] == []
    assert r.json()["ppl"] == 0


def test_both_or_neither_forms_rejected(session_factory, tmp_path):
    c = _app(session_factory, tmp_path)
    assert c.post("/grants", json={"recipient": "r", "ppl": 1,
                                   "allowed_types": ["PERSON"]}).status_code == 422
    assert c.post("/grants", json={"recipient": "r"}).status_code == 422
    assert c.post("/grants", json={"recipient": "r", "ppl": 4}).status_code == 422


def test_explicit_types_report_ppl_only_on_exact_match(session_factory, tmp_path):
    c = _app(session_factory, tmp_path)
    r = c.post("/grants", json={"recipient": "r", "allowed_types": ["PERSON"]})
    assert r.status_code == 201 and r.json()["ppl"] is None


def test_reveal_groups_by_legal_basis_and_audits_categories(
        session_factory, tmp_path, mem_store, mem_index, fake_embedder,
        born_digital_pii_pdf):
    kp = InMemoryKeyProvider()
    with session_factory() as s:
        doc = ingest(s, mem_store, born_digital_pii_pdf)
        s.commit()
        process(s, doc.id, mem_store,
                anonymizer=Pseudonymizer(kp, PostgresMappingStore(s)),
                search_index=mem_index, embedder=fake_embedder)
        s.commit()
    gs = InMemoryGrantStore()
    grant = gs.issue("r", ["EMAIL"], actor="mark", document_id=doc.id)
    r = _app(session_factory, tmp_path, kp, gs).post(
        f"/documents/{doc.id}/reveal",
        json={"grant_id": grant.grant_id, "types": ["EMAIL", "BSN", "GEZONDHEID"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["by_legal_basis"]["Art. 6"] == {"revealed": ["EMAIL"],
                                                "withheld": ["BSN"]}
    assert body["by_legal_basis"]["Art. 9"] == {"revealed": [], "withheld": ["GEZONDHEID"]}
    flat = {t for g in body["by_legal_basis"].values() for v in g.values() for t in v}
    assert flat == set(body["revealed_types"]) | set(body["withheld_types"])
    with session_factory() as s:
        rec = s.execute(select(AuditRecord).where(
            AuditRecord.step == "deanonymize")).scalar_one()
    assert rec.payload["categories"] == ["c1"]
    assert PII_BSN not in str(rec.payload)
    meta = _app(session_factory, tmp_path, kp, gs).get(f"/documents/{doc.id}").json()
    assert meta["pii_counts_by_category"]["c1"] == 3  # bsn + iban + email
    assert meta["pii_counts_by_category"]["c2"] == 0


def test_cli_issue_with_ppl(monkeypatch):
    seen = {}
    monkeypatch.setattr("wordsworth.client._post_json",
                        lambda url, path, payload, timeout=30: seen.update(
                            payload=payload) or {"grant_id": "g1"})
    assert cli_main(["--url", "http://api", "grant", "issue",
                     "--recipient", "r", "--ppl", "2"]) == 0
    assert seen["payload"] == {"recipient": "r", "ppl": 2}
