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

`wordsworth-ingest --corpus-dir <dir> --dossier <dossier> --manifest
<manifest.jsonl> --pilot-report <check.json>` ingests a fetched corpus against
a provenance manifest instead of the API's per-request `source_url`/
`fetched_at` — for a batch fetched once by a script or by hand, not uploaded
file by file. Without `--manifest`, `wordsworth-ingest` behaves exactly as
before.

**The manifest** is one JSONL record per file: `bestand` (the file name,
matching the key `fetch_woo_corpus.py` and `wordsworth-dossier-uit-herkomst`
already use), `url`, `fetched_at` (ISO-8601 with a timezone) and `sha256`.
Every fetcher writes it (`wordsworth.manifest.append_entry`); extra fields
(e.g. `besluit`, `bytes`) are accepted and ignored. Before any file is
ingested:

- every `*.pdf` in the corpus directory must have a manifest entry — an
  unlisted file aborts the whole run, naming the file;
- every file's sha256 must match its entry — a mismatch fails loudly, naming
  the file and both digests;
- every backend (object store, OpenAnonymiser, OpenSearch, embeddings) must be
  configured and a declared homelab one (`WORDSWORTH_HOMELAB_HOSTS`) — alma, or
  a backend not configured at all, is refused, never defaulted;
- the `--pilot-report` file must record a completed robots.txt/terms/Anubis
  check (who, when, the quoted robots.txt and terms, the Anubis status) with
  decision `proceed` — a missing field or a decision other than `proceed`
  refuses the run.

Each document is then ingested with the entry's `url` as `source_url` and the
entry's `fetched_at` — **never the ingest time**, which would make the
provenance look complete when it only repeats when wordsworth happened to run.

**Read-back is the proof.** After each ingest, the document's `register`
audit record is read back and compared with the manifest. A document whose
recorded provenance is missing or differs — including a manifest file whose
bytes were already a live document, in this dossier or another, with other or
no provenance — fails with the reason; it is not reprocessed, and the run
exits non-zero. A duplicate delivery therefore **keeps its first recorded
provenance**; recording provenance on a re-delivery changes what `ingest()`
promises and is its own, separate OpenSpec change.

A layer that did not run — OpenAnonymiser being down included — fails the run;
no document is reported as indexed when that happens.
