import pytest

from wordsworth.generator import (
    DeterministicGenerator,
    GenerationError,
    Generator,
    OllamaGenerator,
    Source,
)


def test_deterministic_generator_satisfies_protocol():
    assert isinstance(DeterministicGenerator(), Generator)


def test_injected_generator_produces_the_answer():
    gen = DeterministicGenerator()
    sources = [Source("d1", "de gemeente besluit"), Source("d2", "notulen")]
    answer = gen.generate("waarover besluit de gemeente?", sources)
    # The injected generator's answer is used, and it cites the given source ids.
    assert "waarover besluit de gemeente?" in answer.text
    assert answer.citations == ["d1", "d2"]


def test_local_model_unavailable_fails_loudly_no_cloud_fallback():
    # An unreachable local Ollama must raise, never silently fall back anywhere.
    gen = OllamaGenerator(url="http://127.0.0.1:1", model="llama3.1")
    with pytest.raises(GenerationError):
        gen.generate("vraag", [Source("d1", "tekst")])
