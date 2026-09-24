## ADDED Requirements

### Requirement: A superseded document leaves the index

The `SearchIndex` protocol SHALL provide `delete(doc_id)`, and superseding a
document SHALL remove its entry, so a search never returns the same stored
object twice.

#### Scenario: Copies no longer show up in search

- **WHEN** a document with an index entry is superseded
- **THEN** its entry is gone and a search that matched it returns only the
  surviving document
