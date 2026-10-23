## ADDED Requirements

### Requirement: Corpus ingest against a manifest

`wordsworth-ingest` SHALL accept an optional `--manifest`, a record per file of
`file`, `url`, `fetched_at` (ISO-8601 with a timezone), `sha256`, `bytes`,
`status` and `ok`, in one format for
every fetcher. With a manifest, a `*.pdf` in the corpus directory that has no
entry SHALL abort the whole run before any file is ingested, and a file whose
sha256 differs from its entry SHALL fail loudly. Each document SHALL be
ingested with the entry's `url` as `source_url` and the entry's `fetched_at`,
which SHALL never be replaced by the ingest time. Without `--manifest`, ingest
behaviour SHALL be unchanged.

#### Scenario: Provenance reaches the audit record

- **WHEN** a corpus is ingested with a manifest
- **THEN** each document's `register` audit record carries the manifest's
  `source_url` and `fetched_at`

#### Scenario: A file without an entry aborts the run

- **WHEN** the corpus directory holds a PDF the manifest does not list
- **THEN** the run aborts naming the file, and no file is ingested

#### Scenario: A file that is not the one the manifest describes

- **WHEN** a file's sha256 differs from its manifest entry
- **THEN** the run fails and names the file and both digests

#### Scenario: A manifest written by the fetcher is ingested

- **WHEN** a manifest is written the way the fetcher writes it and then
  ingested
- **THEN** every entry is accepted and its provenance is recorded

### Requirement: Recorded provenance is read back after ingest

After each document is ingested from a manifest, the audit record SHALL be read
back, and the document SHALL fail, with the reason, if `source_url` or
`fetched_at` is missing from the `register` record or differs from the
manifest. A run in which any document failed SHALL exit non-zero.

#### Scenario: The bytes were already a document

- **WHEN** a manifest file's bytes are already a live document, in the same
  dossier or in another one, with other or no provenance
- **THEN** that document fails with the reason that the recorded provenance
  differs from the manifest, and the run exits non-zero

#### Scenario: Matching provenance passes

- **WHEN** the `register` record carries the manifest's `source_url` and
  `fetched_at`
- **THEN** the document is not failed on provenance

### Requirement: A manifest run uses homelab backends only

A run with `--manifest` SHALL require the environment variable
`WORDSWORTH_BACKEND_ENV` to be `homelab`, and SHALL refuse to start when it is
missing, empty, `alma` or any other value. The backend SHALL NOT be inferred
from backend URLs or hosts, and `WORDSWORTH_BACKEND_ENV` SHALL NOT be
defaulted.

#### Scenario: A non-homelab backend

- **WHEN** `WORDSWORTH_BACKEND_ENV` is `alma`
- **THEN** the run is refused before any file is ingested

#### Scenario: A missing backend

- **WHEN** `WORDSWORTH_BACKEND_ENV` is unset or empty
- **THEN** the run is refused, not defaulted

### Requirement: A layer that did not run fails the run

In a manifest run, a document that does not reach `indexed` because a layer did
not run, OpenAnonymiser being down included, SHALL be reported as failed and
SHALL make the run exit non-zero. It SHALL NOT be reported as a success.

#### Scenario: OpenAnonymiser is down

- **WHEN** OpenAnonymiser is unreachable during a manifest run
- **THEN** the run fails and no document is reported as indexed

### Requirement: A manifest needs a completed pilot check

`wordsworth-ingest` SHALL refuse a manifest whose pilot report has no completed
robots.txt, terms and Anubis check recording who, when and the decision
`proceed`. A decision other than `proceed` SHALL stop the run.

#### Scenario: No completed check

- **WHEN** the pilot report has no completed check
- **THEN** the run is refused and nothing is ingested

#### Scenario: Decision is stop

- **WHEN** the recorded decision is not `proceed`
- **THEN** the run is refused and nothing is ingested
