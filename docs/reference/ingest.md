---
status: draft
last_reviewed: 2026-10-23
---

# `POST /ingest`

Uploads one or more PDFs (`multipart/form-data`, field `files`) and drives
each through the full straat: ingest → OCR recovery (if scanned) → anonymize →
store → index. See `/docs` (Swagger) for the live schema; this page is the
parameters and what they cause to be recorded.

## Parameters

| name | required | what |
| --- | --- | --- |
| `files` | yes | one or more PDFs |
| `dossier` | yes | the dossier these documents belong to; a document in none is invisible to every scoped search |
| `domain` | no | pseudonymisation domain for the batch; default `WORDSWORTH_DEFAULT_DOMAIN` |
| `source_url` | no | where the bytes were fetched from. `https://` with a host, at most 2048 characters. A malformed value is refused: `400` with the reason, nothing ingested |
| `fetched_at` | no | when the bytes were fetched, ISO-8601 with a timezone (e.g. `2026-10-20T09:30:00+00:00`). A malformed value is refused the same way |

`source_url` and `fetched_at` apply to every file in one request — one upload
is one delivery from one place. Neither is required: an unpublished document
has no URL, and omitting both leaves ingest exactly as it was before these
parameters existed.

## What is recorded

For every ingested document, wordsworth computes `source_sha256` itself — the
sha256 of the uploaded bytes, the same digest the content-addressed object key
already carries. **It is never taken from the request**: a client-supplied
hash would only repeat what the client claims, and would prove nothing.

`source_url`, `fetched_at` (when given) and `source_sha256` (always) are
written to:

- the `documents` row (`source_url`, `fetched_at`, `source_sha256` columns,
  all nullable), and
- the `register` step of that document's append-only audit record — so the
  hash-chained trail proves them too, not only the current row.

`GET /documents/{id}` returns all three top-level (`source_url`, `fetched_at`,
`source_sha256`), and the full `register` payload under `steps`.

## A page with no text layer

A document whose text extraction and OCR recovery together yield no text ends
in a visible error state (`unprocessable_ocr`, shown by the API and the
console) and is never indexed — never an empty text pushed into the search
index. See the `document-lifecycle` spec for the state machine.
