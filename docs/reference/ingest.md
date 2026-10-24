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

The batch CLI (`wordsworth-ingest`, `src/wordsworth/ingest_corpus.py`) accepts
an optional `--manifest <file>` alongside `--corpus-dir`/`--dossier`, plus a
required `--pilot-report <file>` when `--manifest` is given. Without
`--manifest`, behaviour is unchanged.

**Manifest format**, one JSON record per line, one shared format for every
fetcher (`scripts/eval/fetch_woo_corpus.py` writes it via
`wordsworth.ingest_manifest.manifest_record`):

| field | what |
| --- | --- |
| `file` | the file name in `--corpus-dir` |
| `url` | `source_url` — `https://` with a host, as `provenance.validate_source_url` checks |
| `fetched_at` | ISO-8601 with a timezone — recorded as-is, **never** replaced by the ingest time |
| `sha256` | checked against the file's own hash; a mismatch fails the run and names both digests |
| `bytes`, `status`, `ok` | carried through; not otherwise validated by ingest |

Checks run **before any file is ingested**: `WORDSWORTH_BACKEND_ENV` (below),
the pilot report, every `*.pdf` has a manifest entry (an unlisted file aborts
the whole run), and every file's sha256 matches its entry.

**`WORDSWORTH_BACKEND_ENV` is required** for a manifest run: `homelab` or the
run is refused — missing, empty, `alma`, or anything else. Never defaulted,
never inferred from backend URLs or hosts (both clusters resolve under
`*.svc.cluster.local`, so a host cannot tell them apart).

**Read-back is the proof.** After each document is ingested, the `register`
audit record is read back and compared with the manifest's `url`/`fetched_at`.
Missing or differing provenance fails that document with the reason, and the
run exits non-zero — this is how a duplicate delivery is caught: `ingest()`'s
key is still `documents/<sha256>`, so bytes already a live document (in this
dossier or another one) keep their **first** recorded provenance; the new
manifest's provenance never overwrites it, and the read-back fails that
document rather than reporting it as ingested. The dossier membership is
still added (unchanged: the key ignores the dossier), only the provenance
claim is what fails.

A layer that did not run (OpenAnonymiser down included) also fails the run
for that document — it is never reported as a success.

See `evaluation.md`'s "published-dossier pilot" section for the gate order
(pilot report → manifest/corpus checks → ingest) and
`openspec/changes/pilot-ingest-manifest/` for the full spec.
