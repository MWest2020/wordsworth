## REMOVED Requirements

### Requirement: Stub downstream transitions

**Reason**: No lifecycle transition is a stub anymore — `index` is now real (see
the added "Indexing transition" requirement); `extract` and `anonymize` were made
real in a prior change.
**Migration**: The `index` step now pushes the anonymized text to the search
index before transitioning to `indexed`. See "Indexing transition".

## ADDED Requirements

### Requirement: Indexing transition

The `anonymize → index → indexed` transition SHALL read the document's persisted
anonymized text and push it to the injected `SearchIndex` before transitioning to
`indexed`. Indexing SHALL be idempotent (upsert by document id). Index failure
SHALL be treated as transient: it SHALL NOT mark the document `failed`, the run
SHALL NOT commit, and re-processing SHALL complete indexing.

#### Scenario: Indexed document reaches the index

- **WHEN** the index step runs on an `anonymized` document
- **THEN** its anonymized text is present in the search index and the document
  moves to `indexed`

#### Scenario: Index outage is retryable, not a failure

- **WHEN** the search index is unavailable during the index step
- **THEN** the document is not marked `failed`, nothing from that run commits, and
  re-processing with a healthy index completes indexing
