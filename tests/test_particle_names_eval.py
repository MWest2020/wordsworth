"""particle-names-measured: the eval seam sees the particle rule as its own
opt-in layer, default layers unchanged (step 4 of 4, split from
`detect-dutch-particle-names`, #285)."""
from __future__ import annotations

from pathlib import Path

import httpx

from wordsworth.eval import overdetection_run, pii_run
from wordsworth.eval.pii_run import DEFAULT_LAYERS, build_detect

PARTICLE_TEXT = "Pieter ter Berg was aanwezig."
FIX = Path(__file__).parent / "fixtures" / "pii_gold_synthetic.jsonl"


class _StubResponse:
    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return {"entities_found": []}


def test_dutch_particle_name_layer_detects_person():
    detect = build_detect(["dutch_particle_name"])
    preds = detect(PARTICLE_TEXT)
    assert len(preds) == 1
    assert preds[0].entity_type == "PERSON"
    assert preds[0].layer == "dutch_particle_name"


def test_default_layers_with_a_stub_client_miss_the_particle_name(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _StubResponse())
    detect = build_detect(DEFAULT_LAYERS.split(","))
    assert detect(PARTICLE_TEXT) == []


def test_pii_run_default_layers_are_deterministic_and_openanonymiser(monkeypatch):
    seen = {}

    def spy(layers):
        seen["layers"] = layers
        return build_detect(["deterministic"])  # offline stand-in; no network

    monkeypatch.setattr(pii_run, "build_detect", spy)
    assert pii_run.main([str(FIX)]) == 0
    assert seen["layers"] == DEFAULT_LAYERS.split(",") == ["deterministic", "openanonymiser"]


def test_overdetection_run_default_layers_are_deterministic_and_openanonymiser(
    monkeypatch, tmp_path
):
    seen = {}

    def spy(layers):
        seen["layers"] = layers
        return build_detect(["deterministic"])  # offline stand-in; no network

    monkeypatch.setattr(overdetection_run, "build_detect", spy)
    monkeypatch.setattr(overdetection_run, "reachable", lambda timeout=5.0: False)
    out_path = tmp_path / "report.md"
    assert overdetection_run.main([str(FIX), "--out", str(out_path)]) == 0
    assert seen["layers"] == DEFAULT_LAYERS.split(",") == ["deterministic", "openanonymiser"]
    text = out_path.read_text(encoding="utf-8")
    assert f"layers: {DEFAULT_LAYERS}" in text
    assert "not run" in text
