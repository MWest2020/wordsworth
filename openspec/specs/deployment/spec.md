# deployment Specification

## Purpose
TBD - created by archiving change add-deployment-entrypoints. Update Purpose after archive.
## Requirements
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

### Requirement: HTTP document ingestion endpoint

The servable API SHALL expose `POST /ingest`, accepting one or more uploaded
PDFs (multipart field `files`) and driving each through the full pipeline —
ingest, OCR recovery when the document is unprocessable without OCR, anonymize,
store, index. The response SHALL report each file individually (filename,
document id, terminal state, and on failure an error identifier), plus the total
and indexed counts. A file that fails SHALL NOT abort the batch. The endpoint
SHALL be registered only when the object store, database, search index and
embedder are wired, and SHALL anonymize with the OpenAnonymiser driver by
default. It SHALL fail-hard and leak no document text: a per-file failure carries
no clear text and leaves nothing partial indexed.

Ingestion SHALL be idempotent against the search index: a document whose
content key is already present in the index SHALL be skipped (reported as
`skipped`, not re-processed and not duplicated). Because the index is the source
of truth for what is searchable, recreating the index makes those documents
eligible for ingestion again, so a re-run rebuilds exactly what is missing.

#### Scenario: A batch is driven to indexed

- **WHEN** one or more PDFs are POSTed to `/ingest` with the backends reachable
- **THEN** each is anonymized and indexed, and the response reports every file's
  document id and `indexed` state

#### Scenario: Already-indexed document is skipped

- **WHEN** a PDF whose content is already in the index is POSTed again
- **THEN** it is reported `skipped` and not duplicated in the index

#### Scenario: A failing file does not abort the batch

- **WHEN** a batch contains a file that fails (e.g. not a valid PDF, or the
  anonymizer service is down)
- **THEN** that file is reported with an error identifier and no clear text, the
  other files are still processed, and nothing partial is left indexed

#### Scenario: Endpoint absent without a store

- **WHEN** the app is built without an object store wired
- **THEN** `/ingest` is not registered (read-only surface only)

### Requirement: API client CLI

The system SHALL provide a dependency-free client CLI (`wordsworth`, alias
`wordsworthctl`) for the HTTP API, able to check health, ingest a file or a
directory (walked, batched to `POST /ingest`, with a per-file and summary report
that includes each file's processing duration and PII counts), search (lexical
and hybrid), ask (RAG), and query a document's state and metadata. The API base
URL and defaults SHALL be configurable via a command-line flag, an environment
variable, and a persistent config file, with a `config` subcommand to show and
set the file. The base URL SHALL be resolved in the order: flag, then environment
variable, then config file, then a built-in default.

#### Scenario: Ingest a directory via the CLI

- **WHEN** `wordsworth ingest <directory>` is run against a reachable API
- **THEN** the PDFs under the directory are uploaded in batches and a per-file
  result (with duration and PII counts) plus an indexed/total summary is printed

#### Scenario: Missing path is rejected

- **WHEN** `wordsworth ingest` is given a path that does not exist
- **THEN** it exits non-zero without contacting the API

#### Scenario: Base URL comes from the config file

- **WHEN** the API URL has been saved with `wordsworth config --url <url>` and no
  flag or environment variable is set
- **THEN** subsequent commands use that URL without needing `--url`

#### Scenario: Query document metadata

- **WHEN** `wordsworth meta <id>` is run against a reachable API
- **THEN** it prints the document's state, duration, PII counts and step trail

### Requirement: Queryable document metadata

The API SHALL expose `GET /documents/{id}` returning per-document metadata derived
from the append-only audit chain: the current state, total and per-step
processing duration, the PII redaction counts recorded at the anonymize step,
page/byte metrics, and the ordered step trail. It SHALL return 404 for an unknown
document. The metadata SHALL be derived (no new schema). The ingest response SHALL
additionally carry, per file, the processing duration and PII counts.

#### Scenario: Metadata for an ingested document

- **WHEN** `GET /documents/{id}` is called for a document that has been processed
- **THEN** the response reports its state, a total processing duration, the PII
  redaction counts, and the per-step trail

#### Scenario: Unknown document

- **WHEN** `GET /documents/{id}` is called for an id with no audit records
- **THEN** the API returns 404

#### Scenario: Ingest reports timing and counts

- **WHEN** a document is ingested via `POST /ingest`
- **THEN** its per-file result includes the processing duration and the PII counts

### Requirement: Bounded backend concurrency

The service SHALL bound the number of concurrent calls it makes to the
memory-heavy backends — the OpenAnonymiser anonymization service and the Ollama
embedder — so that concurrent ingest callers cannot exceed those backends'
capacity. The limits SHALL be configurable. Exceeding the limit SHALL cause
callers to wait for a slot, not to fan out unbounded requests at the backend.
This SHALL NOT change the anonymize step's behaviour or output.

#### Scenario: Concurrent ingests do not exceed the anonymizer limit

- **WHEN** more ingest requests are in flight than the configured anonymize
  concurrency
- **THEN** no more than that many anonymize calls run against the OpenAnonymiser
  service at once; the rest wait for a slot

#### Scenario: Anonymize behaviour is unchanged

- **WHEN** a document is anonymized under the concurrency limiter
- **THEN** the redaction result and fail-hard behaviour are identical to running
  it without the limiter

### Requirement: Explicit database connection pool sizing

The SQLAlchemy engine SHALL configure its connection pool explicitly
(`pool_size` and `max_overflow`) from configuration rather than relying on
library defaults, so the pool is a deliberate contract sized to the expected
concurrent request volume. The engine SHALL also guard against stale
connections (pre-ping / recycle).

#### Scenario: Pool size is configurable

- **WHEN** the pool size is configured and the engine is created
- **THEN** the engine's pool reflects the configured size rather than the library
  default

#### Scenario: Stale connections do not surface as request errors

- **WHEN** a pooled connection has gone stale between requests
- **THEN** it is validated/recycled before use rather than failing the request

