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

```bash
wordsworth-ingest --corpus-dir ./corpus --dossier zaak-a \
    --manifest ./corpus/manifest.jsonl --pilot-report ./check.json
```

The stricter path for a fetched corpus whose provenance must be proven, not
merely passed along. The manifest is one JSONL record per file, the same
format every fetcher writes (`wordsworth.manifest.ManifestEntry`,
`scripts/eval/fetch_woo_corpus.py`): `file`, `url`, `fetched_at` (ISO-8601 with
a timezone, the real download time), `sha256`, `bytes`, `status`, `ok`.

Every guard that needs no backend runs before anything is touched:

1. **`WORDSWORTH_BACKEND_ENV` must be `homelab`.** Missing, empty, `alma` or
  any other value refuses the run. Never inferred from a backend URL or host
  (both clusters resolve `*.svc.cluster.local`), never defaulted.
2. **`--pilot-report`** must be a JSON file recording a completed check: who
  (`checked_by`), when (`checked_at`), the quoted `robots_txt` and `terms`,
  the `anubis` status, and `decision: "proceed"`. Anything else (missing
  fields, or a decision that is not `proceed`) refuses the run.
3. **Every `*.pdf` in `--corpus-dir` must have a manifest entry**, and the
  script's own sha256 of the file's bytes must match it. A mismatch or an
  unlisted file aborts the whole run before any file is ingested — this is
  checked as one pass over all files, not file by file.

Only then are the sovereign backends wired. Each document is ingested with
the manifest entry's `url` as `source_url` and its `fetched_at`, which is
**never** replaced by the ingest time. After each ingest commits, the
`register` audit record is read back and compared with the manifest entry;
a document whose recorded `source_url` or `fetched_at` is missing or differs
**fails that document, with the reason**. This is what catches the duplicate-
delivery case: `ingest()`'s key is `documents/<sha256>`, so a file already
ingested (in this dossier or another one) returns the *existing* document,
whose `register` record still carries whoever registered it first — the
read-back is the proof that this run's provenance did or did not land, since
duplicate delivery itself is unchanged (see "Not changed" below).

A layer that did not run — OpenAnonymiser down included — fails that document
the same way (the reason names the exception), and makes the whole run exit
non-zero. No document is ever reported as indexed when it is not.

**Not changed:** what `ingest()` does with a duplicate. The object key still
ignores the dossier, and an existing live document still wins; recording
provenance on re-delivery is its own future change.
