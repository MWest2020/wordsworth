"""add-detection-confidence: layer + score per detection; per-layer aggregates in
the anonymize audit record and metadata; threshold counts but never redacts less."""
import pytest

from wordsworth.anonymizer import DeterministicAnonymizer
from wordsworth.detection_stats import DetectionStats
from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import InMemoryMappingStore
from wordsworth.openanonymiser_driver import (
    AnonymizationEngineError, Entity, OpenAnonymiserAnonymizer,
)
from wordsworth.pseudonymizer import ReversibleAnonymizer

PII_BSN = "123456782"


def test_stats_aggregate_min_max_and_threshold():
    st = DetectionStats(min_score=0.8)
    for sc in (0.7, 0.9, 0.95):
        st.add("openanonymiser", "person", sc)
    d = st.to_dict()["openanonymiser"]["PERSON"]
    assert d == {"count": 3, "min_score": 0.7, "max_score": 0.95, "below_threshold": 1}


def test_deterministic_layer_reports_certainty():
    r = DeterministicAnonymizer().anonymize(f"BSN {PII_BSN} en {PII_BSN}")
    assert r.detections["deterministic"]["BSN"] == {
        "count": 2, "min_score": 1.0, "max_score": 1.0, "below_threshold": 0}
    assert "IBAN" not in r.detections["deterministic"]  # zero counts are not rows


def test_reversible_path_merges_layers_and_never_records_values(monkeypatch):
    monkeypatch.setenv("WORDSWORTH_DETECTION_MIN_SCORE", "0.8")
    text = f"Janine van Dijk woont in Haarlem, BSN {PII_BSN}."
    ents = [Entity("PERSON", "Janine van Dijk", 0, 15, "openanonymiser", 0.5),
            Entity("LOCATION", "Haarlem", 25, 32, "openanonymiser", 0.9)]
    r = ReversibleAnonymizer(InMemoryKeyProvider(), InMemoryMappingStore(),
                             detect=lambda t: ents).anonymize(text)
    # threshold never weakens redaction: the 0.5 entity is still a token
    assert "Janine van Dijk" not in r.text and "Haarlem" not in r.text
    oa = r.detections["openanonymiser"]
    assert oa["PERSON"] == {"count": 1, "min_score": 0.5, "max_score": 0.5,
                            "below_threshold": 1}
    assert oa["LOCATION"]["below_threshold"] == 0
    assert r.detections["deterministic"]["BSN"]["count"] == 1
    flat = str(r.detections)
    for secret in ("Janine", "Haarlem", PII_BSN):
        assert secret not in flat


def test_missing_service_score_is_hard_error(monkeypatch):
    import httpx

    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"anonymized_text": "x", "entities_found": [
                {"entity_type": "PERSON", "text": "Jan", "start": 0, "end": 3}]}

    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResp())
    with pytest.raises(AnonymizationEngineError):
        ReversibleAnonymizer(InMemoryKeyProvider(), InMemoryMappingStore()).anonymize(
            "Jan is hier")
    with pytest.raises(AnonymizationEngineError):
        OpenAnonymiserAnonymizer().anonymize("Jan is hier")


def test_service_score_is_preserved(monkeypatch):
    import httpx
    from wordsworth.openanonymiser_driver import detect_entities

    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"anonymized_text": "x", "entities_found": [
                {"entity_type": "PERSON", "text": "Jan", "start": 0, "end": 3,
                 "score": 0.85}]}

    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResp())
    (e,) = detect_entities("Jan is hier")
    assert e.score == 0.85 and e.layer == "openanonymiser"


def test_audit_and_metadata_carry_aggregates(session_factory, mem_store, mem_index,
                                             fake_embedder, born_digital_pii_pdf):
    from fastapi.testclient import TestClient
    from wordsworth.api import create_app
    from wordsworth.pipeline import ingest, process
    with session_factory() as s:
        doc = ingest(s, mem_store, born_digital_pii_pdf)
        s.commit()
        process(s, doc.id, mem_store, search_index=mem_index, embedder=fake_embedder)
        s.commit()
    meta = TestClient(create_app(session_factory=session_factory)).get(
        f"/documents/{doc.id}").json()
    assert meta["counts"] == {"bsn": 1, "iban": 1, "email": 1}
    assert meta["detections"]["deterministic"]["BSN"]["count"] == 1
    assert PII_BSN not in str(meta["detections"])


def test_irreversible_driver_reports_both_layers(monkeypatch):
    import httpx

    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"anonymized_text": "<PERSON> woont in <LOCATION>", "entities_found": [
                {"entity_type": "PERSON", "text": "Jan", "start": 0, "end": 3, "score": 0.6},
                {"entity_type": "LOCATION", "text": "Haarlem", "start": 13, "end": 20,
                 "score": 0.95}]}

    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResp())
    r = OpenAnonymiserAnonymizer().anonymize(f"Jan woont in Haarlem, BSN {PII_BSN}")
    assert r.detections["deterministic"]["BSN"]["count"] == 1
    assert r.detections["openanonymiser"]["PERSON"]["min_score"] == 0.6
    assert r.detections["openanonymiser"]["LOCATION"]["count"] == 1
    assert "Haarlem" not in str(r.detections) and PII_BSN not in str(r.detections)


def test_two_tuple_engine_double_still_yields_deterministic_aggregates():
    r = OpenAnonymiserAnonymizer(engine=lambda t: (t, {"person": 2})).anonymize(
        f"BSN {PII_BSN} en iemand")
    assert r.counts["person"] == 2
    assert r.detections == {"deterministic": {"BSN": {
        "count": 1, "min_score": 1.0, "max_score": 1.0, "below_threshold": 0}}}


def test_spanless_entity_without_score_still_fails_hard(monkeypatch):
    import httpx
    from wordsworth.openanonymiser_driver import detect_entities

    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"anonymized_text": "x", "entities_found": [
                {"entity_type": "PERSON", "text": "Jan"}]}  # no span, no score

    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResp())
    with pytest.raises(AnonymizationEngineError):
        detect_entities("Jan is hier")
