## ADDED Requirements

### Requirement: Pluggable cache

Caching SHALL be accessed through a `Cache` protocol (get/set) with an in-memory
default, so the backend is swappable.

#### Scenario: Set then get returns the value

- **WHEN** a value is set under a key and then fetched
- **THEN** the stored value is returned

### Requirement: Content-addressed embedding cache

Embeddings SHALL be cached keyed by model and a content hash of the input text,
so identical text reuses the vector and a model change does not reuse a stale one.
Because `Embedder.embed` takes a batch (`list[str]`), the cache SHALL key
**per element**, not per batch: on a batched call each text is looked up
individually, only cache misses are embedded (as a sub-batch), and results are
reassembled in input order. The model identifier SHALL be supplied to the cache
wrapper explicitly — the `Embedder` protocol declares only `dim`/`embed`, so
`.model` cannot be assumed (the test `DeterministicEmbedder` has none).

#### Scenario: Identical text reuses the cached embedding

- **WHEN** the same text is embedded twice with caching enabled
- **THEN** the second call returns the cached vector without recomputing

#### Scenario: A batch reuses cached elements and embeds only the misses

- **WHEN** a batch contains some texts already cached and some new
- **THEN** the cached texts are served from cache, only the new texts are
  embedded, and the returned vectors match the input order

### Requirement: Caching never changes results

A cache miss SHALL recompute the same result the uncached path produces; caching
SHALL affect only latency, never outputs. To hold this, the query-result cache
key SHALL include **every parameter that affects the output** — mode, query,
`size`, AND `recall` (the recall size changes the candidate set cosine orders, so
omitting it would serve a result computed under a different recall). Failed
embeddings SHALL NOT be cached. Invalidation/bypass SHALL be available for
re-index or model changes.

#### Scenario: Miss recomputes identically

- **WHEN** a cache miss occurs
- **THEN** the recomputed result equals the uncached result

#### Scenario: Different recall does not collide

- **WHEN** the same query and size are searched with different `recall` values
- **THEN** each uses a distinct cache key and neither serves the other's result

#### Scenario: Invalidation prevents stale results

- **WHEN** the cache is invalidated after a re-index
- **THEN** subsequent queries recompute against the new state
