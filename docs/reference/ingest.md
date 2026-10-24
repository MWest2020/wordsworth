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

## `wordsworth-ingest --manifest` (pilot-ingest-manifest)

`wordsworth-ingest --corpus-dir DIR --dossier NAME --manifest manifest.jsonl
--pilot-report check.json` is the same entry point as a plain corpus ingest,
with stricter rules for provenance that must be proved rather than passed
along. A manifest is one JSON object per line, one shared format for every
fetcher (`fetch_woo_corpus.py` writes it; a person fetching by hand writes the
same fields): `file`, `url`, `fetched_at` (ISO-8601 with a timezone — the real
download time, never the ingest time), `sha256`, `bytes`, `status`, `ok`.

Checks run before any file is ingested: `WORDSWORTH_BACKEND_ENV` must be
`homelab` (required, never defaulted, never inferred from backend URLs — see
`config.py`); the pilot report (`--pilot-report`) must hold a completed check
(`who`, `when`, `robots`, `terms`, `anubis`, `decision`), and the decision must
be `proceed`; every `*.pdf` in the corpus directory must have a manifest
entry, and every file's computed sha256 must match it. Any one of these
failing refuses the whole run before a single file is touched.

**Read-back is the proof.** After each document is ingested and processed,
its `register` audit record is read back and compared with the manifest's
`url` and `fetched_at`. A document that is missing or differs fails with the
reason, and the run's exit status is non-zero. This is how a duplicate
delivery is caught: `ingest()`'s content-addressed key means a pilot PDF
already live as a document — in this dossier or another, from the existing
corpus or from an earlier manifest run — keeps its first provenance;
`register_live()` returns the existing document unchanged. The read-back
is the only place that catches this, and **it fails the document, not the
other way round** — the duplicate's original provenance is never overwritten.

A document that does not reach `indexed` because a layer did not run —
OpenAnonymiser being down included — is reported as failed, not as a success
with a note.
