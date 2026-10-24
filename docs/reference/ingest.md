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

## `wordsworth-ingest --manifest` — manifest-driven corpus ingest

`wordsworth-ingest` (`src/wordsworth/ingest_corpus.py`) accepts an optional
`--manifest <file>` alongside `--corpus-dir` and `--dossier`. Without it,
ingest behaves exactly as before. With it, the stricter rules below apply —
one entry point for both a scripted fetch and a person fetching by hand, so a
pilot-only script never drifts from the one ingest path.

### Manifest format

One JSONL record per file, the same format every fetcher writes
(`wordsworth.manifest.manifest_line`/`read_manifest`):

| field | what |
| --- | --- |
| `file` | the file name, as it sits in `--corpus-dir` |
| `url` | where the bytes were fetched from |
| `fetched_at` | when they were fetched, ISO-8601 with a timezone |
| `sha256` | the fetcher's own digest of the bytes |
| `bytes` | their size |
| `status` | the fetch's HTTP status |
| `ok` | whether the fetch succeeded |

Before anything is ingested:

- a `*.pdf` in `--corpus-dir` with no manifest entry **aborts the whole run**,
  naming the file;
- every file's sha256 is **recomputed from the bytes on disk** and checked
  against its manifest entry — the manifest's sha256 is never trusted over the
  bytes — and a mismatch aborts the whole run, naming the file and both
  digests;
- `check.json` (below) must pass.

Each document is then ingested with the entry's `url` as `source_url` and the
entry's `fetched_at` as `fetched_at`. **`fetched_at` always comes from the
manifest** — it is never replaced by the time ingest itself ran; that would
make an incomplete provenance record look complete.

### Read-back: the proof, not a re-run

After each document is ingested (and committed), the script reads back that
document's `register` audit record and compares `source_url` and `fetched_at`
with the manifest entry. A difference, or either field missing, fails that
document with the reason, and the run's exit status is non-zero.

This is the check that catches the pitfall `ingest()` doesn't close on its
own: the object key is `documents/<sha256 of the bytes>`, and a byte-identical
file already ingested (in this dossier or in another one) makes
`register_live()` return the **existing** document — silently keeping its old
(possibly empty) provenance rather than recording the new delivery. A
duplicate delivery therefore **keeps its first recorded provenance and fails
the manifest run**; it does not overwrite it. (Recording provenance on
re-delivery would change what a document's provenance means once it exists —
that needs its own change, and is out of scope here.)

### Homelab only

A manifest run requires the environment variable `WORDSWORTH_BACKEND_ENV` to
be exactly `homelab`. Missing, empty, `alma`, or any other value refuses the
run before any file is touched. The backend is never inferred from a backend
URL or host (both clusters resolve under `*.svc.cluster.local`, so a host
allow-list or DNS resolution cannot tell them apart) and is never defaulted —
a default would be a silent fallback.

### A layer that did not run fails the run

In a manifest run, a document that does not reach `indexed` because some
layer did not run — OpenAnonymiser being unreachable included — is reported
as failed, never as a success with a note, and the run's exit status is
non-zero.

### `check.json` — the pilot's completed check

A manifest run refuses to start unless `check.json`, a JSON object **in the
same directory as `manifest.jsonl`**, passes. Required fields:

`checked_by`, `checked_at` (ISO-8601 with a timezone), `robots_txt_url`,
`robots_txt` (verbatim), `paths_used`, `paths_disallowed_used`, `terms`,
`anubis`, `user_agent`, `delay_seconds`, `decision`.

The gate passes only when every field above is present, `paths_disallowed_used`
is empty, and `decision` is `"proceed"`. Otherwise the manifest is refused and
the refusal names the failed condition:

- `check.json` missing next to the manifest;
- a required field missing;
- `paths_disallowed_used` not empty (a disallowed path was fetched);
- `decision` is not `"proceed"` (e.g. `"stop"`).

There is no flag or config path for `check.json` — it always sits next to the
manifest it gates, so there is nothing to mis-point. See
`docs/reference/evaluation.md` ("The published-dossier pilot") for the gate
order (check, then manifest, then ingest) in context.
