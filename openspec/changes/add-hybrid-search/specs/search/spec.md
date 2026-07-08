## MODIFIED Requirements

### Requirement: Search index protocol

Indexing and search SHALL be accessed through a `SearchIndex` protocol returning
typed `Hit` results, so the backend is swappable and the pipeline never depends
on a concrete search engine. Indexing SHALL accept an optional per-document
vector, and the protocol SHALL provide a `hybrid_search` method that returns an
RRF-fused recall set carrying each candidate's vector.

#### Scenario: A custom index is used when injected

- **WHEN** a caller injects an object satisfying the `SearchIndex` protocol
- **THEN** the pipeline uses it for the index step instead of the default

#### Scenario: Hybrid recall returns candidates with vectors

- **WHEN** `hybrid_search` is called with a query and a query vector
- **THEN** it returns RRF-fused candidates, each carrying its stored vector for
  the final cosine ranking
