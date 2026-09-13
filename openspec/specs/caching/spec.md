# caching Specification

## Purpose

Making repeated work cheap without making results depend on history.

The one requirement that matters: **caching never changes results.** A cache that
can alter an answer turns every bug report into an archaeology exercise, because
the same input no longer implies the same output.

The embedding cache is **content-addressed** for the same reason — the key is the
content, so a stale entry is not a possible state rather than an unlikely one.
The cache is pluggable because "none" has to be a supported configuration when
you are trying to reproduce something.
## Requirements
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
SHALL affect only latency, never outputs. The query-result cache key SHALL include
**every parameter that affects the output** — mode, query, `size`, AND `recall`
(the recall size changes the candidate set cosine orders, so omitting it would
serve a result computed under a different recall). Failed embeddings SHALL NOT be
cached. Invalidation/bypass SHALL be available for re-index or model changes.

#### Scenario: Different recall does not collide

- **WHEN** the same query and size are searched with different `recall` values
- **THEN** each uses a distinct cache key and neither serves the other's result

#### Scenario: Miss recomputes identically

- **WHEN** a cache miss occurs
- **THEN** the recomputed result equals the uncached result

