"""EUDI-aligned VC gate on the reveal endpoint (ADR-0003), DB-backed.

A presented X-VC credential can only NARROW what the grant allows. Mirrors the
reveal harness in tests/test_reveal_api.py; runs in CI against Postgres, skips
locally without a DB. The pure gate logic is covered locally in tests/test_vc.py.
"""
from __future__ import annotations

from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from wordsworth.api import create_app
from wordsworth.grants import InMemoryGrantStore
from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.pipeline import ingest, process
from wordsworth.pseudonymizer import Pseudonymizer
from wordsworth.vc import issue_sdjwt_vc

PII_BSN = "123456782"
PII_EMAIL = "jan.jansen@haarlem.nl"
VCT = "https://wordsworth/eudi/reveal-authorization"
ISS = "https://issuer.gemeente.example"


def _prepare(session_factory, mem_store, mem_index, fake_embedder, pdf):
    kp = InMemoryKeyProvider()
    with session_factory() as s:
        doc = ingest(s, mem_store, pdf)
        s.commit()
        process(s, doc.id, mem_store,
                anonymizer=Pseudonymizer(kp, PostgresMappingStore(s)),
                search_index=mem_index, embedder=fake_embedder)
        s.commit()
        return kp, doc.id


def _vc(key, types):
    return issue_sdjwt_vc(key, vct=VCT, issuer=ISS,
                          selective_claims={"authorized_types": types})


def test_vc_narrows_grant_to_intersection(session_factory, mem_store, mem_index,
                                          fake_embedder, born_digital_pii_pdf):
    kp, doc_id = _prepare(session_factory, mem_store, mem_index, fake_embedder,
                          born_digital_pii_pdf)
    gs = InMemoryGrantStore()
    grant = gs.issue("agent-x", ["EMAIL", "BSN"], actor="mark", document_id=doc_id)
    key = ec.generate_private_key(ec.SECP256R1())
    client = TestClient(create_app(session_factory=session_factory, key_provider=kp,
                                   grant_store=gs, vc_public_key=key.public_key(),
                                   vc_expected_vct=VCT, vc_expected_issuer=ISS))
    # grant allows EMAIL+BSN, VC authorizes only EMAIL → reveal narrows to EMAIL.
    r = client.post(f"/documents/{doc_id}/reveal",
                    json={"grant_id": grant.grant_id, "types": ["EMAIL", "BSN"]},
                    headers={"X-VC": _vc(key, ["EMAIL"]).present()})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["revealed_types"] == ["EMAIL"]
    assert "BSN" in body["withheld_types"]
    assert PII_EMAIL in body["revealed_text"]
    assert PII_BSN not in body["revealed_text"]


def test_vc_required_without_header_is_403(session_factory, mem_store, mem_index,
                                           fake_embedder, born_digital_pii_pdf):
    kp, doc_id = _prepare(session_factory, mem_store, mem_index, fake_embedder,
                          born_digital_pii_pdf)
    gs = InMemoryGrantStore()
    grant = gs.issue("agent-x", ["EMAIL"], actor="mark", document_id=doc_id)
    key = ec.generate_private_key(ec.SECP256R1())
    client = TestClient(create_app(session_factory=session_factory, key_provider=kp,
                                   grant_store=gs, vc_public_key=key.public_key(),
                                   vc_required=True))
    r = client.post(f"/documents/{doc_id}/reveal", json={"grant_id": grant.grant_id})
    assert r.status_code == 403


def test_invalid_vc_is_403(session_factory, mem_store, mem_index, fake_embedder,
                           born_digital_pii_pdf):
    kp, doc_id = _prepare(session_factory, mem_store, mem_index, fake_embedder,
                          born_digital_pii_pdf)
    gs = InMemoryGrantStore()
    grant = gs.issue("agent-x", ["EMAIL"], actor="mark", document_id=doc_id)
    key = ec.generate_private_key(ec.SECP256R1())
    wrong = ec.generate_private_key(ec.SECP256R1())
    client = TestClient(create_app(session_factory=session_factory, key_provider=kp,
                                   grant_store=gs, vc_public_key=key.public_key()))
    # credential signed by a different issuer key → rejected.
    r = client.post(f"/documents/{doc_id}/reveal",
                    json={"grant_id": grant.grant_id},
                    headers={"X-VC": _vc(wrong, ["EMAIL"]).present()})
    assert r.status_code == 403


def test_no_vc_configured_is_grant_only(session_factory, mem_store, mem_index,
                                        fake_embedder, born_digital_pii_pdf):
    # Gate off (no issuer key) → X-VC ignored, behaviour unchanged.
    kp, doc_id = _prepare(session_factory, mem_store, mem_index, fake_embedder,
                          born_digital_pii_pdf)
    gs = InMemoryGrantStore()
    grant = gs.issue("agent-x", ["EMAIL"], actor="mark", document_id=doc_id)
    client = TestClient(create_app(session_factory=session_factory, key_provider=kp,
                                   grant_store=gs))
    r = client.post(f"/documents/{doc_id}/reveal", json={"grant_id": grant.grant_id},
                    headers={"X-VC": "garbage"})
    assert r.status_code == 200
    assert r.json()["revealed_types"] == ["EMAIL"]
