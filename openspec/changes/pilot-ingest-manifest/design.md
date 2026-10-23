# Design: manifest-driven ingest with a read-back

## Choices

- **Extend `ingest_corpus.py`.** One ingest path. `--manifest` is optional, so
  without it behaviour is as today. With it, the stricter rules below apply.
- **One shared manifest record per file:** `url`, `fetched_at` (the real
  download time, ISO-8601 with timezone), `sha256`. Every fetcher writes it, and
  ingest reads it. The fetcher and the ingest are tested against each other:
  write a record the way the fetcher does, then ingest it.
- **Checks run before any ingest** where they can: every `*.pdf` has an entry
  (an unlisted file aborts the whole run, it is not skipped), and every file's
  sha256 matches its entry. Also before: backends are homelab, and the pilot
  report holds a completed check.
- **`fetched_at` comes from the manifest, always.** Falling back to the ingest
  time would be a silent fallback that makes provenance look complete.
- **Read-back is the proof.** After each `ingest()` and commit, read the
  document's `register` audit record and compare `source_url` and `fetched_at`
  with the manifest. This reads the artefact the system produced, not a re-run
  of the logic (AGENTS.md: "measure the artefact").
- **Duplicate keys fail, and ingest is left alone.** Because the key is
  `documents/<sha256>` and `register_live()` returns the existing document, a
  pilot PDF already ingested keeps its old provenance. The read-back catches
  that and fails the document with the reason. This holds for a duplicate in
  the same dossier and in another one.
- **A layer that did not run is a failure.** A document that did not reach
  `indexed` because a layer did not run (OpenAnonymiser down included) fails the
  run; it is not reported as a success with a note. The exit status is non-zero.
- **Gate order is checked by the script, proven by git.** The script refuses a
  manifest whose pilot report has no completed check (who, when, quoted
  robots.txt and terms, Anubis status, decision `proceed`). Git order (check
  committed before manifest) is proven by the pilot report, not by the script.

## Settled (were open questions in proposal.md)

- **Homelab marker.** A declared allow-list, `WORDSWORTH_HOMELAB_HOSTS`
  (comma-separated hostnames/suffixes), checked against the hostname of each
  configured backend URL (S3 endpoint, OpenAnonymiser, OpenSearch, Ollama) —
  no DNS resolution, no network call, so the guard runs before any file is
  touched. Empty by default, so nothing passes until an operator declares the
  homelab hosts explicitly: the safe default for a guard whose only job is
  refusing an accidental run against alma. A backend whose URL has no value at
  all (only possible for the S3 endpoint today) fails as "missing"; everything
  else fails as "not a homelab backend" until listed.
- **The manifest's file-identifying key is `bestand`**, not a new `filename`.
  `fetch_woo_corpus.py`'s `herkomst.jsonl` and `dossier_tools.by_filename`
  already read/write that key; inventing a second name would silently break
  both the moment the fetcher "moved to the shared format". `url` and
  `fetched_at` are wordsworth's existing ingest-records-source vocabulary.
  `bytes` and `besluit` (the Woo decision page, read by
  `wordsworth.eval.woo_collection`) are kept as extra, fetcher-specific fields
  the shared reader accepts and ignores.
- **Where the pilot report lives:** the script does not guess a path. A
  `--pilot-report <file>` argument is required alongside `--manifest`
  (refused with usage otherwise) — the file itself, including its path
  convention, is `pilot-report-template`'s to define; this change only reads
  whatever file it is pointed at and checks the fields named above.

## Rejected

- **A pilot-only ingest script.** It would drift from the first path.
- **Changing ingest to record provenance on re-delivery.** It changes a
  promise (what a document's provenance means once it exists); it needs its own
  OpenSpec change. Reported as a pilot finding.
- **Adding the dossier to the object key.** Same reason, and it would break
  one-document-per-object.
- **Defaulting a missing backend to homelab,** or to whatever the environment
  holds. A default is a silent fallback.
- **Taking `fetched_at` from file mtime or ingest time** when the manifest lacks
  it. A manifest entry without it is invalid.
- **Trusting the manifest's sha256 over the bytes.** The script hashes the file;
  the manifest only has to agree.

## Tests

The change touches a seam, so the tests call both ends:

1. **Provenance reaches the audit record end to end.** Ingest with a manifest,
   then assert `source_url` and `fetched_at` in the `register` audit record. A
   manifest-parser unit test alone does not count.
2. **Fetcher-written record, then ingest.** Write a manifest as the fetcher
   does, ingest it.
3. **Unlisted file aborts the run,** and nothing is ingested.
4. **sha256 mismatch fails loudly.**
5. **Duplicate key, same dossier and another dossier:** the read-back fails the
   document with the reason; the exit status is non-zero.
6. **Missing and non-homelab backend refused,** alma included.
7. **OpenAnonymiser down:** the run fails.
8. **Report without a completed check, or with decision other than `proceed`,
   is refused.**
