## ADDED Requirements

### Requirement: Servable API composition root

The system SHALL provide a module exposing an ASGI `app` wired to the real
backends from configuration, so a standard ASGI server (e.g.
`uvicorn wordsworth.serve:app`) serves the full read surface — document state,
metrics, search, hybrid search, and ask — not only `/health`. Backends SHALL be
lazy: importing the module SHALL perform no network I/O, and an unavailable
backend SHALL fail only the individual request that needs it (no fallback).

#### Scenario: Full route set is served

- **WHEN** the composition root builds the app
- **THEN** the app exposes the document-state, metrics, search, hybrid and ask
  routes (not the health-only app)

#### Scenario: Import performs no I/O

- **WHEN** the module is imported
- **THEN** no connection to Postgres, OpenSearch or Ollama is opened

### Requirement: Corpus ingestion entrypoint

The system SHALL provide a CLI entrypoint that ingests a directory of PDF
documents through the full pipeline — `ingest → OCR recovery (when a document is
unprocessable without OCR) → anonymize → store → index` — wired to the sovereign
backends from configuration (S3 object store, the OpenAnonymiser GLiNER service,
OpenSearch, Ollama embeddings). It SHALL use the OpenAnonymiser anonymizer, not
the deterministic-only default, and SHALL fail-hard (no clear-text pass-through,
no silent skip) on any step failure.

#### Scenario: A corpus is driven to indexed

- **WHEN** the entrypoint runs against a directory of PDFs with the backends
  reachable
- **THEN** each document is anonymized with the OpenAnonymiser driver and reaches
  the indexed state (scanned documents via OCR recovery first)

#### Scenario: Missing corpus directory is rejected

- **WHEN** the entrypoint is invoked with a corpus directory that does not exist
- **THEN** it exits non-zero without contacting any backend

### Requirement: Idempotent schema bootstrap

The system SHALL provide a CLI entrypoint that creates the database schema and
the append-only audit trigger idempotently, runnable once before serving or
ingesting.

#### Scenario: Bootstrap creates the schema

- **WHEN** the bootstrap entrypoint runs against an empty database
- **THEN** the tables and the append-only audit trigger are created

#### Scenario: Bootstrap is idempotent

- **WHEN** the bootstrap entrypoint runs again against an already-initialised
  database
- **THEN** it succeeds without error and leaves the schema unchanged
