"""add-detection-feedback: typed allow/deny lists, hash in audit, feedback event."""
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from wordsworth.api import create_app
from wordsworth.detection_lists import DetectionLists
from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import InMemoryMappingStore
from wordsworth.models import AuditRecord
from wordsworth.openanonymiser_driver import Entity, OpenAnonymiserAnonymizer
from wordsworth.pseudonymizer import ReversibleAnonymizer

PII_BSN = "123456782"


def _lists(tmp_path, allow=None, deny=None):
    (tmp_path / "allow.json").write_text(json.dumps(allow or {}))
    (tmp_path / "deny.json").write_text(json.dumps(deny or {}))
    return DetectionLists.load(tmp_path)


def test_typed_false_positive_is_suppressed_never_across_types(tmp_path):
    lists = _lists(tmp_path, allow={"PERSON": ["^Jansen BV$"]})
    text = "Jansen BV leverde aan Jan Jansen."
    ents = [Entity("PERSON", "Jansen BV", 0, 9, "openanonymiser", 0.8),
            Entity("PERSON", "Jan Jansen", 22, 32, "openanonymiser", 0.9)]
    r = ReversibleAnonymizer(InMemoryKeyProvider(), InMemoryMappingStore(),
                             detect=lambda t: ents, lists=lists).anonymize(text)
    assert r.text.startswith("Jansen BV")          # kept in clear (not PII)
    assert "Jan Jansen" not in r.text              # real person still redacted
    assert r.detections["suppressed_by_list"]["PERSON"]["count"] == 1
    assert r.lists_hash == lists.hash and len(lists.hash) == 64
    # same pattern, other type → kept
    org = [Entity("ORGANIZATION", "Jansen BV", 0, 9, "openanonymiser", 0.8)]
    r2 = ReversibleAnonymizer(InMemoryKeyProvider(), InMemoryMappingStore(),
                              detect=lambda t: org, lists=lists).anonymize(text)
    assert "Jansen BV" not in r2.text


def test_deny_adds_list_layer_detections_in_both_drivers(tmp_path):
    lists = _lists(tmp_path, deny={"KENTEKEN": [r"\b[A-Z]{2}-\d{3}-[A-Z]\b"]})
    text = f"Voertuig AB-123-C van BSN {PII_BSN}."
    rev = ReversibleAnonymizer(InMemoryKeyProvider(), InMemoryMappingStore(),
                               detect=lambda t: [], lists=lists).anonymize(text)
    assert "AB-123-C" not in rev.text and "[KENTEKEN:" in rev.text
    assert rev.detections["list"]["KENTEKEN"]["count"] == 1
    irr = OpenAnonymiserAnonymizer(engine=lambda t: (t, {}), lists=lists).anonymize(text)
    assert "AB-123-C" not in irr.text and "[KENTEKEN]" in irr.text
    assert irr.detections["list"]["KENTEKEN"]["count"] == 1
    assert irr.detections["deterministic"]["BSN"]["count"] == 1
    assert irr.lists_hash == lists.hash


def test_no_lists_is_a_noop_with_no_hash():
    lists = DetectionLists.load("")
    assert lists.hash is None
    ents = [Entity("PERSON", "Jan", 0, 3, "openanonymiser", 0.9)]
    kept, suppressed = lists.apply("Jan", ents)
    assert kept == ents and suppressed == {}


def test_malformed_list_is_hard_error(tmp_path):
    (tmp_path / "allow.json").write_text("[1,2]")
    with pytest.raises(ValueError):
        DetectionLists.load(tmp_path)
    (tmp_path / "allow.json").write_text('{"PERSON": ["("]}')
    with pytest.raises(Exception):
        DetectionLists.load(tmp_path)


def test_hash_changes_with_content(tmp_path):
    a = _lists(tmp_path, allow={"PERSON": ["^A$"]}).hash
    b = _lists(tmp_path, allow={"PERSON": ["^B$"]}).hash
    assert a != b


def test_feedback_is_audited_without_values_and_lists_untouched(
        session_factory, mem_store, mem_index, fake_embedder, born_digital_pii_pdf,
        tmp_path):
    from wordsworth.pipeline import ingest, process
    lists = _lists(tmp_path, allow={"PERSON": ["^X$"]})
    before = lists.hash
    with session_factory() as s:
        doc = ingest(s, mem_store, born_digital_pii_pdf)
        s.commit()
        process(s, doc.id, mem_store, search_index=mem_index, embedder=fake_embedder)
        s.commit()
    c = TestClient(create_app(session_factory=session_factory))
    r = c.post(f"/documents/{doc.id}/feedback",
               json={"kind": "fp", "type": "person", "token": "[PERSON:3fa9c2d1]"})
    assert r.status_code == 201, r.text
    assert r.json()["recorded"] == {"kind": "fp", "type": "PERSON", "token": "[PERSON:3fa9c2d1]"}
    # a clear value cannot be smuggled in as a token; no free-text field exists
    assert c.post(f"/documents/{doc.id}/feedback",
                  json={"kind": "fp", "type": "PERSON", "token": "Jan Jansen"}).status_code == 422
    assert c.post(f"/documents/{doc.id}/feedback",
                  json={"kind": "fp", "type": "PERSON", "note": "Jan"}).status_code == 201
    assert c.post(f"/documents/{doc.id}/feedback",
                  json={"kind": "maybe", "type": "PERSON"}).status_code == 422
    with session_factory() as s:
        recs = s.execute(select(AuditRecord).where(
            AuditRecord.step == "detection_feedback")).scalars().all()
        assert len(recs) == 2 and all("Jan" not in json.dumps(r.payload) for r in recs)
        assert recs[0].from_state == recs[0].to_state == "indexed"
        anon = s.execute(select(AuditRecord).where(AuditRecord.step == "anonymize")
                         ).scalar_one()
        assert anon.payload["lists_hash"] is None       # pipeline ran without lists
    assert DetectionLists.load(tmp_path).hash == before  # lists untouched
    meta = c.get(f"/documents/{doc.id}").json()
    assert meta["lists_hash"] is None and "lists_hash" not in meta["counts"]
