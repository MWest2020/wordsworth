## ADDED Requirements

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

## MODIFIED Requirements

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
