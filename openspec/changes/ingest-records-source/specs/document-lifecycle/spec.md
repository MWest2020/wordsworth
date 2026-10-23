## ADDED Requirements

### Requirement: A document records where it came from

`/ingest` SHALL accept an optional `source_url` (`https://`, with a host, at
most 2048 characters) and an optional `fetched_at` (ISO-8601 with a timezone),
and SHALL reject a malformed value with status 400 and the reason. For every
ingested document, wordsworth SHALL record `source_sha256`, the sha256 of the
uploaded bytes, computed by wordsworth and never taken from the request. It
SHALL record that together with the two fields, when given, on the document and
in the ingest audit record. Omitting both fields SHALL leave ingest behaviour
unchanged.

#### Scenario: Provenance reaches the audit record

- **WHEN** a PDF is posted to `/ingest` with a valid `source_url` and
  `fetched_at`
- **THEN** the document and its ingest audit record carry both values and the
  sha256 of the uploaded bytes

#### Scenario: A malformed URL is refused

- **WHEN** `source_url` is `ftp://x` or has no host
- **THEN** the request fails with 400 and says why, and nothing is ingested

#### Scenario: No provenance, no change

- **WHEN** a PDF is posted without `source_url` and `fetched_at`
- **THEN** it is ingested exactly as before, with `source_sha256` still
  recorded

### Requirement: A document without text is never indexed silently

A document whose text extraction and OCR recovery together yield no text SHALL
end in a visible error state and SHALL NOT be indexed.

#### Scenario: A scan OCR cannot read

- **WHEN** a PDF has no text layer and OCR returns no text
- **THEN** the document is in an error state that the API and the console
  show, and the search index holds nothing for it
