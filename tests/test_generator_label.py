# SPDX-License-Identifier: MIT
"""`Generator.label` op beide drivers (topic-labels-llm).

Ollama zonder Ollama: `urlopen` in `wordsworth.generator` wordt vervangen door
een nep-transport dat een vast HTTP-antwoord teruggeeft of een fout gooit.
"""
from __future__ import annotations

import io
import json

import pytest

from wordsworth import generator as gen_mod
from wordsworth.generator import (DeterministicGenerator, GenerationError,
                                  Generator, OllamaGenerator)
from wordsworth.topic_labels import prompt, validate


def _transport(monkeypatch, response: str | None = None, fout: Exception | None = None):
    gezien = []

    def urlopen(req, timeout=None):
        gezien.append(json.loads(req.data))
        if fout is not None:
            raise fout
        return io.BytesIO(json.dumps({"response": response}).encode())

    monkeypatch.setattr(gen_mod.urllib.request, "urlopen", urlopen)
    return gezien


def _ollama():
    return OllamaGenerator(url="http://ollama.test:11434", model="llama3.2:3b")


def test_ollama_returns_the_json_object_and_asks_for_json(monkeypatch):
    gezien = _transport(monkeypatch, json.dumps(
        {"label": "Kap van bomen", "description": "Over kappen."}))

    antwoord = _ollama().label("de prompt")

    assert antwoord == {"label": "Kap van bomen", "description": "Over kappen."}
    (verzoek,) = gezien
    assert verzoek["prompt"] == "de prompt"
    assert verzoek["format"] == "json" and verzoek["model"] == "llama3.2:3b"


@pytest.mark.parametrize("response", ["dit is geen json", '["een", "lijst"]', '"tekst"'])
def test_an_answer_that_is_not_a_json_object_is_a_generation_error(monkeypatch,
                                                                   response):
    _transport(monkeypatch, response)
    with pytest.raises(GenerationError):
        _ollama().label("de prompt")


def test_a_transport_failure_is_a_generation_error(monkeypatch):
    _transport(monkeypatch, fout=OSError("connection refused"))
    with pytest.raises(GenerationError):
        _ollama().label("de prompt")


def test_an_unreachable_ollama_fails_loudly():
    gen = OllamaGenerator(url="http://127.0.0.1:1", model="llama3.2:3b", timeout=2)
    with pytest.raises(GenerationError):
        gen.label("de prompt")


def test_the_deterministic_generator_answers_from_the_terms_and_passes_validation():
    gen = DeterministicGenerator()
    assert isinstance(gen, Generator)
    antwoord = gen.label(prompt(["kap", "boom", "vergunning"], ["Een eik."]))
    assert antwoord["label"] == "Over kap boom vergunning"
    assert validate(antwoord) == (antwoord["label"], antwoord["description"])
    assert gen.label(prompt(["kap"], ["x"])) == gen.label(prompt(["kap"], ["y"]))
