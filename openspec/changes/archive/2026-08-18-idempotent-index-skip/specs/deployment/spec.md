## MODIFIED Requirements

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
