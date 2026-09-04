"""add-domain-keys: domain/TYPE key scopes; default domain = legacy scopes;
grants are domain-bound and fail-safe; ingest binds a document to a domain."""
import uuid
import pytest
from fastapi.testclient import TestClient

from wordsworth.api import create_app
from wordsworth.client import main as cli_main
from wordsworth.grants import InMemoryGrantStore, authorize
from wordsworth.key_audit import JsonlKeyLifecycleAudit
from wordsworth.keys import DEFAULT_DOMAIN, InMemoryKeyProvider, scope_for
from wordsworth.mapping_store import InMemoryMappingStore, PostgresMappingStore
from wordsworth.pipeline import document_domain, ingest, process
from wordsworth.pseudonymizer import Pseudonymizer, ReversibleAnonymizer

PII_BSN = "123456782"
PII_EMAIL = "jan.jansen@haarlem.nl"


def test_scope_for_default_domain_is_legacy_plain_type():
    assert scope_for(DEFAULT_DOMAIN, "PERSON") == "PERSON"
    assert scope_for("wi", "PERSON") == "wi/PERSON"
    with pytest.raises(ValueError):
        scope_for("a/b", "PERSON")
    with pytest.raises(ValueError):
        scope_for("wi", "")


def test_domains_do_not_share_pseudonyms():
    kp = InMemoryKeyProvider()
    text = f"BSN {PII_BSN}"
    wi = Pseudonymizer(kp, InMemoryMappingStore(), domain="wi").anonymize(text).text
    mo = Pseudonymizer(kp, InMemoryMappingStore(), domain="mo").anonymize(text).text
    glob = Pseudonymizer(kp, InMemoryMappingStore()).anonymize(text).text
    assert wi != mo and wi != glob and mo != glob
    # same domain, same value → same token (consistency within a domain)
    assert Pseudonymizer(kp, InMemoryMappingStore(), domain="wi").anonymize(text).text == wi


def test_legacy_scope_keeps_working():
    kp = InMemoryKeyProvider()
    legacy_key = kp.current_key("BSN")  # a pre-change key row, scoped by type only
    out = Pseudonymizer(kp, InMemoryMappingStore()).anonymize(f"BSN {PII_BSN}")
    store = InMemoryMappingStore()
    Pseudonymizer(kp, store).anonymize(f"BSN {PII_BSN}")
    token = [t for t in out.text.split() if t.startswith("[BSN:")][0]
    assert store.get(token).key_id == legacy_key.id


def test_reversible_driver_uses_domain_for_entities():
    from wordsworth.openanonymiser_driver import Entity
    kp = InMemoryKeyProvider()
    ents = [Entity("PERSON", "Janine", 0, 6, "openanonymiser", 0.9)]
    a = ReversibleAnonymizer(kp, InMemoryMappingStore(), detect=lambda t: ents,
                             domain="wi").anonymize("Janine woont hier").text
    b = ReversibleAnonymizer(kp, InMemoryMappingStore(), detect=lambda t: ents,
                             domain="mo").anonymize("Janine woont hier").text
    assert a != b and "Janine" not in a + b


def test_grant_without_domain_is_default_only():
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    # Document-scoped, so the domain binding is what is under test rather than
    # the (closed-by-default) global-grant gate.
    d = uuid.uuid4()
    g = InMemoryGrantStore().issue("r", ["BSN"], actor="m", document_id=d)
    assert authorize(g, d, {"BSN"}, now) == {"BSN"}
    assert authorize(g, d, {"BSN"}, now, domain="wi") == set()
    gw = InMemoryGrantStore().issue("r", ["BSN"], actor="m", domain="wi",
                                    document_id=d)
    assert authorize(gw, d, {"BSN"}, now, domain="wi") == {"BSN"}
    assert authorize(gw, d, {"BSN"}, now) == set()


def _client(session_factory, tmp_path, kp, gs, mem_store, mem_index, fake_embedder):
    return TestClient(create_app(
        session_factory=session_factory, key_provider=kp, grant_store=gs,
        store=mem_store, search_index=mem_index, embedder=fake_embedder,
        anonymizer_factory=lambda s, domain=DEFAULT_DOMAIN: ReversibleAnonymizer(
            kp, PostgresMappingStore(s), detect=lambda t: [], domain=domain),
        key_audit=JsonlKeyLifecycleAudit(tmp_path / "k.jsonl")))


def test_ingest_binds_domain_and_reveal_is_domain_gated(
        session_factory, tmp_path, mem_store, mem_index, fake_embedder,
        born_digital_pii_pdf):
    kp, gs = InMemoryKeyProvider(), InMemoryGrantStore()
    c = _client(session_factory, tmp_path, kp, gs, mem_store, mem_index, fake_embedder)
    r = c.post("/ingest", params={"domain": "wi"},
               files=[("files", ("a.pdf", born_digital_pii_pdf, "application/pdf"))])
    assert r.status_code == 200, r.text
    doc_id = r.json()["results"][0]["document_id"]
    assert r.json()["results"][0]["state"] == "indexed"
    with session_factory() as s:
        from uuid import UUID
        assert document_domain(s, UUID(doc_id)) == "wi"
    assert c.get(f"/documents/{doc_id}").json()["domain"] == "wi"

    # a default-domain grant reveals nothing in domain wi (403: not applicable)
    g_default = c.post("/grants", json={"recipient": "r", "allowed_types": ["EMAIL"],
                                        "document_id": doc_id}).json()
    assert g_default["domain"] == DEFAULT_DOMAIN
    assert c.post(f"/documents/{doc_id}/reveal",
                  json={"grant_id": g_default["grant_id"]}).status_code == 403
    # a wi-bound grant does
    g_wi = c.post("/grants", json={"recipient": "r", "allowed_types": ["EMAIL"],
                                   "domain": "wi", "document_id": doc_id}).json()
    r = c.post(f"/documents/{doc_id}/reveal", json={"grant_id": g_wi["grant_id"]})
    assert r.status_code == 200 and PII_EMAIL in r.json()["revealed_text"]
    assert c.post("/ingest", params={"domain": "a/b"},
                  files=[("files", ("b.pdf", born_digital_pii_pdf, "application/pdf"))]
                  ).status_code == 400


def test_legacy_one_arg_factory_still_works_for_default_domain(
        session_factory, tmp_path, mem_store, mem_index, fake_embedder,
        born_digital_pii_pdf):
    kp = InMemoryKeyProvider()
    c = TestClient(create_app(
        session_factory=session_factory, store=mem_store, search_index=mem_index,
        embedder=fake_embedder,
        anonymizer_factory=lambda s: Pseudonymizer(kp, PostgresMappingStore(s))))
    ok = c.post("/ingest", files=[("files", ("a.pdf", born_digital_pii_pdf,
                                              "application/pdf"))])
    assert ok.json()["results"][0]["state"] == "indexed"
    # a non-default domain with a domain-unaware factory is an error, not a
    # silent fall-back to the global keys
    bad = c.post("/ingest", params={"domain": "wi"},
                 files=[("files", ("c.pdf", born_digital_pii_pdf + b"\n%x",
                                   "application/pdf"))])
    assert bad.json()["results"][0]["state"] == "error"


def test_cli_domain_flags(monkeypatch):
    seen = {}
    monkeypatch.setattr("wordsworth.client._post_json",
                        lambda url, path, payload, timeout=30: seen.update(
                            payload=payload) or {"grant_id": "g1"})
    assert cli_main(["--url", "http://api", "grant", "issue", "--recipient", "r",
                     "--types", "BSN", "--domain", "wi"]) == 0
    assert seen["payload"] == {"recipient": "r", "allowed_types": ["BSN"], "domain": "wi"}


def test_rotation_per_domain_scope_is_audited_and_keeps_revealing(tmp_path):
    from wordsworth.escrow import AgeEscrow
    from wordsworth.key_lifecycle import rotate_keys
    from wordsworth.pseudonymizer import _reveal
    kp, store = InMemoryKeyProvider(), InMemoryMappingStore()
    out = Pseudonymizer(kp, store, domain="wi").anonymize(f"BSN {PII_BSN}").text
    mo_out = Pseudonymizer(kp, store, domain="mo").anonymize(f"BSN {PII_BSN}").text
    token, mo_token = out.split()[-1], mo_out.split()[-1]
    old_id, mo_id = store.get(token).key_id, store.get(mo_token).key_id
    audit = JsonlKeyLifecycleAudit(tmp_path / "k.jsonl")
    new = rotate_keys(kp, store, AgeEscrow(), audit, actor="m",
                      scope=scope_for("wi", "BSN"))
    assert store.get(token).key_id == new.id != old_id           # re-encrypted
    assert store.get(mo_token).key_id == mo_id                    # other domain untouched
    assert kp.current_key(scope_for("mo", "BSN")).id == mo_id
    events = (tmp_path / "k.jsonl").read_text()
    assert old_id in events and new.id in events                # rotation audited
    assert '"scope": "wi/BSN"' in events or "'scope': 'wi/BSN'" in events or "wi/BSN" in events
    restored, _ = _reveal(out, None, store.get, kp.key)
    assert PII_BSN in restored
