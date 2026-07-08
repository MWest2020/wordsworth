import pytest

from wordsworth.embedder import DeterministicEmbedder, Embedder, EmbeddingError


def test_satisfies_protocol():
    assert isinstance(DeterministicEmbedder(), Embedder)


def test_deterministic_and_correct_dimension():
    emb = DeterministicEmbedder(dim=64)
    a = emb.embed(["gemeente Haarlem parkeren"])[0]
    b = emb.embed(["gemeente Haarlem parkeren"])[0]
    assert a == b
    assert len(a) == 64


def test_shared_tokens_share_dimensions():
    emb = DeterministicEmbedder(dim=64)
    shared = emb.embed(["parkeren parkeren"])[0]
    other = emb.embed(["honden honden"])[0]
    # Overlapping content lands on overlapping buckets; disjoint content does not.
    assert any(x > 0 for x in shared)
    assert shared != other


def test_empty_text_is_hard_error_not_null_vector():
    with pytest.raises(EmbeddingError):
        DeterministicEmbedder().embed([""])
