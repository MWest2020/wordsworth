## MODIFIED Requirements

### Requirement: Indexing transition

The `anonymize → index → indexed` transition SHALL read the document's persisted
anonymized text, embed it with the injected `Embedder`, and push the text and its
vector to the injected `SearchIndex` before transitioning to `indexed`. Indexing
SHALL be idempotent (upsert by document id). A failed embedding or index failure
SHALL be treated as transient: it SHALL NOT mark the document `failed`, the run
SHALL NOT commit, and re-processing SHALL complete indexing. A null/zero vector
SHALL never be stored.

#### Scenario: Indexed document reaches the index with a vector

- **WHEN** the index step runs on an `anonymized` document
- **THEN** its anonymized text and embedding are present in the search index and
  the document moves to `indexed`

#### Scenario: Index or embedding outage is retryable, not a failure

- **WHEN** the embedder or the search index is unavailable during the index step
- **THEN** the document is not marked `failed`, nothing from that run commits, and
  re-processing with healthy backends completes indexing
