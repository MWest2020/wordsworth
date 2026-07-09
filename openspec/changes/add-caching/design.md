# Design decisions — add-caching

## Seam

```python
class Cache(Protocol):
    def get(self, key: str): ...
    def set(self, key: str, value) -> None: ...
```

Default `LruCache` (in-memory, bounded). A shared backend (Redis) can be added
later behind the same protocol — no new dependency for the PoC.

## What to cache, and the keys

- **Embeddings**: key = `emb:{model}:{sha256(text)}`. Content-addressed, so
  identical text reuses the vector; a model change changes the key (no stale mix).
- **Query results**: key = `q:{mode}:{size}:{query}` for BM25/hybrid. Short TTL or
  explicit invalidation on re-index.

## Correctness rule

A cache miss MUST recompute the exact same result a non-cached path would produce;
the cache never changes outputs, only latency. This keeps caching safe to add and
easy to reason about (and it composes with the nulvector rule: a failed embedding
is never cached).

## Invalidation

Explicit `invalidate(prefix)` / bypass flag, called on re-index or model change.
No implicit staleness that could serve a query against a changed corpus.

## Not in scope

Distributed cache coherence, cache warming, per-tenant partitioning.
