## MODIFIED Requirements

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
