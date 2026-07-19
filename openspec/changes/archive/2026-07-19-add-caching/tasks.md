# Tasks — add-caching

Done = green: every task ships with its tests. NOTE: unchecked — for a Habitat builder.

## 1. Cache seam
- [x] 1.1 `cache.py`: `Cache` protocol + bounded in-memory `LruCache`
- [x] 1.2 Tests: set/get; eviction at bound

## 2. Embedding cache
- [x] 2.1 Wrap the embedder: key `emb:{model}:{sha256(text)}`; do not cache failures
- [x] 2.2 Tests: identical text served from cache; model change -> new key

## 3. Query cache + invalidation
- [x] 3.1 Cache BM25/hybrid results by `{mode}:{size}:{query}`; invalidate/bypass
- [x] 3.2 Tests: miss recomputes identically; invalidation forces recompute
