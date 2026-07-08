## ADDED Requirements

### Requirement: Search index protocol

Indexing and search SHALL be accessed through a `SearchIndex` protocol returning
typed `Hit` results, so the backend is swappable and the pipeline never depends
on a concrete search engine.

#### Scenario: A custom index is used when injected

- **WHEN** a caller injects an object satisfying the `SearchIndex` protocol
- **THEN** the pipeline uses it for the index step instead of the default

### Requirement: Document-level BM25 indexing

The `OpenSearchIndex` driver SHALL index one document per source document (id =
source document id) into a text field analysed with the Dutch analyzer, scored by
BM25. Indexing SHALL be an idempotent upsert.

#### Scenario: Indexed document is retrievable by keyword

- **WHEN** a document's anonymized text is indexed and a query matching its terms
  is searched
- **THEN** the document appears in the ranked hits with a positive score

#### Scenario: Re-indexing the same id does not duplicate

- **WHEN** the same document id is indexed twice
- **THEN** the index holds a single document for that id

### Requirement: Keyword search returns ranked hits

Search SHALL accept a free-text query and return document hits ranked by BM25
score, each carrying the document id and score.

#### Scenario: More relevant document ranks higher

- **WHEN** two documents are indexed and a query matches one far more than the
  other
- **THEN** the stronger match ranks above the weaker one

#### Scenario: Search is exposed over the API

- **WHEN** `GET /search?q=<terms>` is called
- **THEN** it returns the ranked hits for the query
