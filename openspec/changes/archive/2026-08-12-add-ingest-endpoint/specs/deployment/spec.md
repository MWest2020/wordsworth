## ADDED Requirements

### Requirement: HTTP document ingestion endpoint

The servable API SHALL expose `POST /ingest`, accepting an uploaded PDF and
driving it through the full pipeline — ingest, OCR recovery when the document is
unprocessable without OCR, anonymize, store, index — returning the document id
and its terminal state. The endpoint SHALL be registered only when the object
store, database, search index and embedder are wired, and SHALL anonymize with
the OpenAnonymiser driver by default. It SHALL fail-hard and leak no document
text: a failure (including the anonymizer service being unavailable) returns an
error status carrying no clear text, and nothing partial is left indexed.

#### Scenario: A pushed document is driven to indexed

- **WHEN** a PDF is POSTed to `/ingest` with the backends reachable
- **THEN** it is anonymized and indexed, and the response reports the document id
  and the `indexed` state

#### Scenario: Failure leaks no text

- **WHEN** ingestion fails (e.g. the anonymizer service is down)
- **THEN** an error status is returned carrying no document text, and no
  un-redacted content is stored or indexed

#### Scenario: Endpoint absent without a store

- **WHEN** the app is built without an object store wired
- **THEN** `/ingest` is not registered (read-only surface only)
