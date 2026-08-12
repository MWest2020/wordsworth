## MODIFIED Requirements

### Requirement: API client CLI

The system SHALL provide a dependency-free client CLI (`wordsworth`, alias
`wordsworthctl`) for the HTTP API, able to check health, ingest a file or a
directory (walked, batched to `POST /ingest`, with a per-file and summary
report), search, and query a document's state. The API base URL and defaults
SHALL be configurable via a command-line flag, an environment variable, and a
persistent config file, with a `config` subcommand to show and set the file. The
base URL SHALL be resolved in the order: flag, then environment variable, then
config file, then a built-in default.

#### Scenario: Ingest a directory via the CLI

- **WHEN** `wordsworth ingest <directory>` is run against a reachable API
- **THEN** the PDFs under the directory are uploaded in batches and a per-file
  result plus an indexed/total summary is printed

#### Scenario: Missing path is rejected

- **WHEN** `wordsworth ingest` is given a path that does not exist
- **THEN** it exits non-zero without contacting the API

#### Scenario: Base URL comes from the config file

- **WHEN** the API URL has been saved with `wordsworth config --url <url>` and no
  flag or environment variable is set
- **THEN** subsequent commands use that URL without needing `--url`
