# Ingest a fetched corpus against a manifest, and prove the provenance arrived

## Why

Mark, 2026-10-23, to odin: *"kun je met wordsworth een publicatie van de
gemeente gooise meren door de straat halen: ranken en anonimiseren waar nodig."*
The pilot is one published publication as one dossier
(`pilot-gooise-meren-politieke-avond-2026-09-23`, 12 PDFs, candidate A). Its
provenance has to be provable, not merely passed along.

Architect and reviewer, in #general, on the pilot plan:

- **One ingest path.** A pilot-only script would drift from `ingest_corpus.py`
  and rot, so `ingest_corpus.py` gets a `--manifest` option instead.
- **One manifest format for every fetcher.** A scripted fetch and a person
  fetching by hand write the same record: url, fetched_at, sha256. A mix-up
  between manifest and file then fails loudly.
- **The clever pitfall: a green run with no provenance.** `ingest()` builds the
  key as `documents/<sha256 of the bytes>` and `register_live()` returns an
  existing live document, dropping the new `source_url` and `fetched_at`.
  Provenance is written only in the `register` audit record, which is
  append-only. The 567-document dossier `gooise-meren-woo-2022` is already on
  the cluster with unknown provenance. If a pilot PDF is already in it, ingest
  succeeds, adds a dossier membership, keeps the old (empty) provenance, and
  nothing signals it.
- **A layer that did not run is a failure**, OpenAnonymiser being down
  included (the pilot definition in `docs/reference/evaluation.md`).
- **The check comes before the fetch's result is used.** The reviewer: "A
  template that can be filled in afterwards proves nothing." The script refuses
  a manifest whose pilot report has no completed robots/terms/Anubis check.

The fetch itself is done (odin coding session, 2026-10-24): 12/12 PDFs, with a
`check.json` written before the downloads and a `manifest.jsonl` with url,
`fetched_at` (download time), sha256 and bytes per file. Nothing is ingested yet.

## What changes

1. **`ingest_corpus.py --manifest <file>`**, the same entry point
   (`wordsworth-ingest`), no new script.
   - A `*.pdf` in the corpus directory with no manifest entry aborts the whole
     run before anything is ingested.
   - Each file's sha256 is checked against its manifest entry; a mismatch fails
     loudly.
   - `source_url` and the manifest's `fetched_at` are passed to `ingest()`. The
     manifest's `fetched_at` is never replaced by the ingest time.
2. **Read-back after each ingest.** The script reads the document's `register`
   audit record and compares `source_url` and `fetched_at` with the manifest.
   Missing or different fails that document, with the reason. The run exits
   non-zero.
3. **Homelab only.** The backend is named by a required environment variable
   `WORDSWORTH_BACKEND_ENV` (`homelab` or `alma`). A manifest run with it
   missing, empty, or any value other than `homelab` is refused. It is never
   inferred from the backend URLs and never defaulted.
4. **A layer that did not run fails the run**, including OpenAnonymiser down.
5. **Gate order.** The script refuses a manifest unless `check.json`, a JSON
   object in the same directory as `manifest.jsonl`, passes. The file already
   exists in the fetched pilot. Required fields: `checked_by`, `checked_at`
   (ISO-8601 with timezone), `robots_txt_url`, `robots_txt` (verbatim),
   `paths_used`, `paths_disallowed_used`, `terms`, `anubis`, `user_agent`,
   `delay_seconds`, `decision`. The gate passes only when every field is
   present, `paths_disallowed_used` is empty and `decision` is `proceed`;
   otherwise ingest refuses the manifest and says which condition failed.
   A `stop` decision stops the pilot; a fallback to Gelderland is a separate
   decision for Mark.

6. **Code layout.** The manifest logic (`ingest_manifest_corpus`, `_advance`,
   parsing, checks, read-back) lives in its own module; every file stays at
   or under 200 lines (AGENTS.md). `src/wordsworth/ingest_corpus.py` keeps only
   the CLI wiring. It was 94 lines and the first build took it to 214, which
   the reviewer failed.
7. **No scratch or verification artefacts in the repo.** No `.scratch-verify/`
   (`check.json`, `manifest-empty.jsonl`, `run_unlisted.sh`). Evidence goes in
   the PR text.
8. **The herkomst sample** `docs/explanation/meting-woo-corpus-01.herkomst.jsonl`
   is extended, not renamed: each row keeps `bestand`, `bron`, `opgehaald` and
   `besluit` and gains `file`, `url`, `fetched_at` next to them. The fetch
   record stays additive: `wordsworth.eval.woo_collection.build()` reads
   `bestand` and `dossier_tools.by_filename()` reads `bestand` and `besluit`,
   and both must keep working. The first build renamed the keys; `build()` then
   raised `KeyError` and `by_filename()` silently returned an empty mapping, so
   every document counted as `zonder_herkomst`. No test read the sample, so the
   proof for this item was false.

Settled in the amendment (2026-10-24, architect finding on #221: the gate
named no location and no fields): the gate reads `check.json` next to
`manifest.jsonl`, with the fields in item 5, matching the fetched pilot's
existing file. The full report template stays the later change
`pilot-report-template`.

Settled in the amendment (2026-10-24), after the first build failed review and
the second stopped on an open question:

- **Backend identity** is the required variable `WORDSWORTH_BACKEND_ENV`
  (`homelab|alma`), in line with `config.py`'s other environment settings.
  Rejected: a host allow-list (it drifts) and resolving hosts (both clusters
  use `*.svc.cluster.local`).
- **Manifest fields** are `file`, `url`, `fetched_at`, `sha256`, `bytes`,
  `status`, `ok`.
- **The freeze on `~/wordsworth-pilot` stays**: ingest nothing, and do not
  commit the manifest or `check.json`.

Not changed: what `ingest()` does with a duplicate. The key still ignores the
dossier and an existing live document still wins.

## Non-goals

- **Recording provenance on re-delivery.** That would change what ingest
  promises and needs its own change. It goes in the pilot report as an open
  finding; architect may say whether it is worth doing.
- **Repairing the 567-document dossier.** Not this pilot's job.
- **The report template, the fetch, and the gold-set tooling.** Separate
  changes (`pilot-report-template`, gold-set tooling).

## Open questions

- **What happens to a document already in the index with other provenance**
  (the re-delivery case above): fail only, or report as a distinct outcome.
  This change fails it.
