"""Cache seam. Caching is strictly an optimization: a miss recomputes the exact
same result an uncached path would produce, so the cache never changes outputs —
only latency. Failed computations are never cached (this composes with the
nulvector rule: a failed embedding is a hard error, never a cached null-vector).

The default `LruCache` is in-memory and bounded — no new dependency. A shared
backend (e.g. Redis) can be added later behind the same `Cache` protocol.
"""
from __future__ import annotations

import hashlib
from collections import OrderedDict
from typing import Any, Callable, Protocol, runtime_checkable

from .embedder import Embedder


@runtime_checkable
class Cache(Protocol):
    def get(self, key: str) -> Any: ...
    def set(self, key: str, value: Any) -> None: ...
    def invalidate(self, prefix: str = "") -> None: ...


class LruCache:
    """Bounded in-memory LRU. `get` returns None on a miss; the oldest entry is
    evicted first once `maxsize` is exceeded. No stored value is ever None, so
    None unambiguously means 'miss' (embeddings are non-null; results are lists).
    """

    def __init__(self, maxsize: int = 1024):
        if maxsize < 1:
            raise ValueError("maxsize must be >= 1")
        self.maxsize = maxsize
        self._store: OrderedDict[str, Any] = OrderedDict()

    def get(self, key: str) -> Any:
        if key not in self._store:
            return None
        self._store.move_to_end(key)
        return self._store[key]

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value
        self._store.move_to_end(key)
        while len(self._store) > self.maxsize:
            self._store.popitem(last=False)

    def invalidate(self, prefix: str = "") -> None:
        """Drop everything (default) or every key under a prefix — the explicit
        hook for a re-index or model change. No implicit staleness."""
        for key in [k for k in self._store if k.startswith(prefix)]:
            del self._store[key]


def _embedding_key(model: str, text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"emb:{model}:{digest}"


class CachingEmbedder:
    """Wrap an `Embedder`, caching vectors keyed by model + content hash. Identical
    text reuses the vector; a model change changes the key (no stale mix). A failed
    embedding raises before anything is stored, so failures are never cached."""

    def __init__(self, inner: Embedder, cache: Cache, model: str | None = None):
        self.inner = inner
        self.cache = cache
        self.model = model or getattr(inner, "model", inner.__class__.__name__)

    @property
    def dim(self) -> int:
        return self.inner.dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        results: list[Any] = [None] * len(texts)
        missing: list[int] = []
        for i, text in enumerate(texts):
            cached = self.cache.get(_embedding_key(self.model, text))
            if cached is not None:
                results[i] = cached
            else:
                missing.append(i)
        if missing:
            # inner.embed raises on failure -> we never reach the caching loop,
            # so a failed embedding is never cached.
            fresh = self.inner.embed([texts[i] for i in missing])
            for i, vector in zip(missing, fresh):
                self.cache.set(_embedding_key(self.model, texts[i]), vector)
                results[i] = vector
        return results


QUERY_PREFIX = "q:"


def query_key(mode: str, size: int, query: str) -> str:
    return f"{QUERY_PREFIX}{mode}:{size}:{query}"


def cached_query(
    cache: Cache,
    mode: str,
    size: int,
    query: str,
    recompute: Callable[[], Any],
    *,
    bypass: bool = False,
) -> Any:
    """Return a cached query result or recompute-and-store it. `bypass=True` always
    recomputes and refreshes the entry — the explicit escape hatch after a re-index
    or model change. Invalidate the whole family with `cache.invalidate(QUERY_PREFIX)`.
    A miss recomputes exactly what the uncached path would; the cache only saves work.
    """
    key = query_key(mode, size, query)
    if not bypass:
        cached = cache.get(key)
        if cached is not None:
            return cached
    result = recompute()
    cache.set(key, result)
    return result
