"""End-to-end reversible-mode composition through the deployed-style factories
(add-wire-reversible-mode). DB-backed → runs in CI, skips locally without a DB.

Uses a FakeTransit + a SHARED in-memory key vault to stand in for OpenBao + the
Postgres key_vault (durable across requests), exactly as production shares them
via the DB. Proves: ingest via `anonymizer_factory` pseudonymises reversibly with
durable keyed tokens, and a later reveal via `key_provider_factory` +
`grant_store_factory` resolves those keys (durability across requests) and reveals
only the granted type."""
from __future__ import annotations

from fastapi.testclient import TestClient

from wordsworth.api import create_app
from wordsworth.grants import PostgresGrantStore
from wordsworth.keys import DurableKeyProvider
from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.pseudonymizer import ReversibleAnonymizer
from wordsworth.transit import FakeTransit, InMemoryKeyVaultStore

PII_BSN = "123456782"
PII_EMAIL = "jan.jansen@haarlem.nl"


def test_reversible_wiring_end_to_end(session_factory, mem_store, mem_index,
                                      fake_embedder, born_digital_pii_pdf):
    # Shared, durable-across-requests backends (stand-ins for OpenBao + DB vault).
    vault = InMemoryKeyVaultStore()
    transit = FakeTransit()
    no_entities = lambda text: []   # deterministic PII only; keeps the test hermetic

    def key_provider(session):
        return DurableKeyProvider(vault, transit)

    def anonymizer(session):
        return ReversibleAnonymizer(
            key_provider(session), PostgresMappingStore(session), detect=no_entities
        )

    app = create_app(
        session_factory=session_factory,
        search_index=mem_index,
        embedder=fake_embedder,
        store=mem_store,
        anonymizer_factory=anonymizer,
        key_provider_factory=key_provider,
        grant_store_factory=lambda s: PostgresGrantStore(s),
    )
    client = TestClient(app)

    # 1. Ingest through the reversible straat (anonymizer_factory).
    r = client.post("/ingest", files={
        "files": ("doc.pdf", born_digital_pii_pdf, "application/pdf")})
    assert r.status_code == 200
    result = r.json()["results"][0]
    assert result["state"] == "indexed"
    doc_id = result["document_id"]

    # 2. Issue a BSN-only grant (durable Postgres grant store).
    with session_factory() as s:
        grant = PostgresGrantStore(s).issue(
            "agent-x", ["BSN"], actor="mark", document_id=doc_id)
        s.commit()
        grant_id = grant.grant_id

    # 3. Reveal via key_provider_factory + grant_store_factory — a FRESH durable
    #    provider over the same vault resolves the keys minted during ingest.
    r = client.post(f"/documents/{doc_id}/reveal",
                    json={"grant_id": grant_id, "types": ["BSN", "EMAIL"]})
    assert r.status_code == 200
    body = r.json()
    assert PII_BSN in body["revealed_text"]        # granted + durable key resolved
    assert PII_EMAIL not in body["revealed_text"]   # not granted → stays token
    assert body["revealed_types"] == ["BSN"]
    assert "EMAIL" in body["withheld_types"]
