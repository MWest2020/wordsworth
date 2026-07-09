"""Caching is an optimization only: a miss must recompute the same result the
uncached path produces. These tests pin that contract and the eviction bound."""
import pytest

from wordsworth.cache import (
    QUERY_PREFIX,
    Cache,
    CachingEmbedder,
    LruCache,
    cached_query,
    query_key,
)
from wordsworth.embedder import DeterministicEmbedder, EmbeddingError


class CountingEmbedder:
    """DeterministicEmbedder that records how many texts it actually computed."""

    def __init__(self, model: str = "det", dim: int = 64):
        self.model = model
        self._inner = DeterministicEmbedder(dim=dim)
        self.dim = dim
        self.calls = 0

    def embed(self, texts):
        self.calls += len(texts)
        return self._inner.embed(texts)


# --- 1. Cache seam --------------------------------------------------------


def test_lru_satisfies_protocol():
    assert isinstance(LruCache(), Cache)


def test_set_then_get_returns_value():
    cache = LruCache()
    cache.set("k", [1.0, 2.0])
    assert cache.get("k") == [1.0, 2.0]


def test_missing_key_returns_none():
    assert LruCache().get("nope") is None


def test_eviction_at_bound_is_oldest_first():
    cache = LruCache(maxsize=2)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)  # evicts "a" (oldest)
    assert cache.get("a") is None
    assert cache.get("b") == 2
    assert cache.get("c") == 3


def test_get_refreshes_recency():
    cache = LruCache(maxsize=2)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.get("a")     # "a" now most-recent
    cache.set("c", 3)  # evicts "b", not "a"
    assert cache.get("a") == 1
    assert cache.get("b") is None


def test_invalidate_prefix_and_all():
    cache = LruCache()
    cache.set("q:bm25:10:x", 1)
    cache.set("emb:det:y", 2)
    cache.invalidate(QUERY_PREFIX)
    assert cache.get("q:bm25:10:x") is None
    assert cache.get("emb:det:y") == 2
    cache.invalidate()  # everything
    assert cache.get("emb:det:y") is None


# --- 2. Embedding cache ---------------------------------------------------


def test_identical_text_served_from_cache():
    inner = CountingEmbedder()
    emb = CachingEmbedder(inner, LruCache())
    first = emb.embed(["gemeente Haarlem parkeren"])
    second = emb.embed(["gemeente Haarlem parkeren"])
    assert first == second
    assert inner.calls == 1  # second call recomputed nothing


def test_batch_only_computes_the_misses():
    inner = CountingEmbedder()
    emb = CachingEmbedder(inner, LruCache())
    emb.embed(["a"])
    out = emb.embed(["a", "b"])  # "a" cached, only "b" recomputed
    assert len(out) == 2
    assert inner.calls == 2


def test_model_change_uses_a_new_key():
    cache = LruCache()
    emb_a = CachingEmbedder(CountingEmbedder(model="model-a"), cache)
    emb_b = CachingEmbedder(CountingEmbedder(model="model-b"), cache)
    emb_a.embed(["text"])
    assert cache.get("emb:model-a:" + _sha("text")) is not None
    assert cache.get("emb:model-b:" + _sha("text")) is None  # different key
    emb_b.embed(["text"])  # recomputes under its own model
    assert cache.get("emb:model-b:" + _sha("text")) is not None


def test_failed_embedding_is_not_cached():
    inner = CountingEmbedder()
    cache = LruCache()
    emb = CachingEmbedder(inner, cache)
    with pytest.raises(EmbeddingError):
        emb.embed([""])  # empty text -> hard error, per nulvector rule
    assert cache.get("emb:det:" + _sha("")) is None


def test_caching_embedder_matches_uncached_output():
    inner = CountingEmbedder()
    emb = CachingEmbedder(inner, LruCache())
    cached = emb.embed(["parkeervergunning Haarlem"])[0]
    uncached = DeterministicEmbedder(dim=64).embed(["parkeervergunning Haarlem"])[0]
    assert cached == uncached


# --- 3. Query cache + invalidation ---------------------------------------


def test_query_key_shape():
    assert query_key("hybrid", 10, "parkeren") == "q:hybrid:10:parkeren"


def test_miss_recomputes_then_hit_is_served():
    cache = LruCache()
    calls = {"n": 0}

    def recompute():
        calls["n"] += 1
        return ["doc-1", "doc-2"]

    first = cached_query(cache, "bm25", 10, "parkeren", recompute)
    second = cached_query(cache, "bm25", 10, "parkeren", recompute)
    assert first == second == ["doc-1", "doc-2"]
    assert calls["n"] == 1  # second served from cache


def test_miss_recomputes_identically_to_uncached():
    cache = LruCache()
    result = cached_query(cache, "bm25", 5, "q", lambda: ["a", "b"])
    assert result == ["a", "b"]  # equals what the bare recompute returns


def test_invalidation_forces_recompute():
    cache = LruCache()
    counter = {"n": 0}

    def recompute():
        counter["n"] += 1
        return counter["n"]

    assert cached_query(cache, "bm25", 10, "q", recompute) == 1
    cache.invalidate(QUERY_PREFIX)  # e.g. after a re-index
    assert cached_query(cache, "bm25", 10, "q", recompute) == 2


def test_bypass_forces_recompute_and_refreshes():
    cache = LruCache()
    counter = {"n": 0}

    def recompute():
        counter["n"] += 1
        return counter["n"]

    assert cached_query(cache, "bm25", 10, "q", recompute) == 1
    assert cached_query(cache, "bm25", 10, "q", recompute, bypass=True) == 2
    # bypass refreshed the entry, so a normal read now serves the new value
    assert cached_query(cache, "bm25", 10, "q", recompute) == 2


def _sha(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()
