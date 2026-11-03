## ADDED Requirements

### Requirement: The running service seals every new original

The API and every ingesting CLI SHALL write and read originals through one
originals store, in every pseudonymisation mode.

#### Scenario: The API's store

- **WHEN** the API starts with an object store configured
- **THEN** its store is an originals store, in reversible and in irreversible
  mode

#### Scenario: A CLI ingest

- **WHEN** a document is ingested with the corpus or manifest CLI
- **THEN** its original is stored sealed
