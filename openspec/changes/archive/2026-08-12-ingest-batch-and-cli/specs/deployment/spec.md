## MODIFIED Requirements

### Requirement: HTTP document ingestion endpoint

The servable API SHALL expose `POST /ingest`, accepting **one or more** uploaded
PDFs (multipart field `files`) and driving each through the full pipeline —
ingest, OCR recovery when the document is unprocessable without OCR, anonymize,
store, index. The response SHALL report each file individually (filename,
document id, terminal state, and on failure an error identifier), plus the total
and indexed counts. A file that fails SHALL NOT abort the batch. The endpoint
SHALL be registered only when the object store, database, search index and
embedder are wired, and SHALL anonymize with the OpenAnonymiser driver by
default. It SHALL fail-hard and leak no document text: a per-file failure
(including the anonymizer service being unavailable) carries no clear text and
leaves nothing partial indexed.

#### Scenario: A batch is driven to indexed

- **WHEN** one or more PDFs are POSTed to `/ingest` with the backends reachable
- **THEN** each is anonymized and indexed, and the response reports every file's
  document id and `indexed` state

#### Scenario: A failing file does not abort the batch

- **WHEN** a batch contains a file that fails (e.g. not a valid PDF, or the
  anonymizer service is down)
- **THEN** that file is reported with an error identifier and no clear text, the
  other files are still processed, and nothing partial is left indexed

#### Scenario: Endpoint absent without a store

- **WHEN** the app is built without an object store wired
- **THEN** `/ingest` is not registered (read-only surface only)

## ADDED Requirements

### Requirement: API client CLI

The system SHALL provide a dependency-free client CLI (`wordsworthctl`) for the
HTTP API, able to check health, ingest a file or a directory (walked, batched to
`POST /ingest`, with a per-file and summary report), search, and query a
document's state. The API base URL SHALL be configurable via a flag and an
environment variable.

#### Scenario: Ingest a directory via the CLI

- **WHEN** `wordsworthctl ingest <directory>` is run against a reachable API
- **THEN** the PDFs under the directory are uploaded in batches and a per-file
  result plus an indexed/total summary is printed

#### Scenario: Missing path is rejected

- **WHEN** `wordsworthctl ingest` is given a path that does not exist
- **THEN** it exits non-zero without contacting the API
