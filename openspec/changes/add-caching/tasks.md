# Tasks — add-caching

Done = green: every task ships with its tests. NOTE: unchecked — for a Habitat builder.

## 1. Cache seam
- [ ] 1.1 `cache.py`: `Cache` protocol + bounded in-memory `LruCache`
- [ ] 1.2 Tests: set/get; eviction at bound

## 2. Embedding cache
- [ ] 2.1 Wrap the embedder: per-element key `emb:{model}:{sha256(text)}` over the
      batch (embed only misses, reassemble in order); model id passed explicitly
      (not read off the embedder); do not cache failures
- [ ] 2.2 Tests: identical text served from cache; a mixed batch embeds only the
      misses in order; model change -> new key

## 3. Query cache + invalidation
- [ ] 3.1 Cache BM25/hybrid results by `{mode}:{size}:{recall}:{query}` (every
      output-affecting param); invalidate/bypass
- [ ] 3.2 Tests: miss recomputes identically; different recall -> distinct key;
      invalidation forces recompute
