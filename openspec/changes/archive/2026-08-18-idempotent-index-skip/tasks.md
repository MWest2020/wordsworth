## 1. Index-based recognition

- [x] 1.1 Add `has_object_key` to the `SearchIndex` protocol + `InMemoryIndex`.
- [x] 1.2 `OpenSearchIndex.has_object_key` via a `count` term-query on object_key.
- [x] 1.3 `/ingest` skip-existing checks the index (not the DB).

## 2. Gate

- [x] 2.1 Tests (InMemoryIndex has_object_key) + full suite green.
