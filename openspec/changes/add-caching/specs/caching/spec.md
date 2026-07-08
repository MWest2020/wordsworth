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

#### Scenario: Identical text reuses the cached embedding

- **WHEN** the same text is embedded twice with caching enabled
- **THEN** the second call returns the cached vector without recomputing

### Requirement: Caching never changes results

A cache miss SHALL recompute the same result the uncached path produces; caching
SHALL affect only latency, never outputs. Failed embeddings SHALL NOT be cached.
Invalidation/bypass SHALL be available for re-index or model changes.

#### Scenario: Miss recomputes identically

- **WHEN** a cache miss occurs
- **THEN** the recomputed result equals the uncached result

#### Scenario: Invalidation prevents stale results

- **WHEN** the cache is invalidated after a re-index
- **THEN** subsequent queries recompute against the new state
