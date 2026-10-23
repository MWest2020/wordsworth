# Design: manifest-driven ingest with a read-back

## Choices

- **Extend `ingest_corpus.py`.** One ingest path. `--manifest` is optional, so
  without it behaviour is as today. With it, the stricter rules below apply.
- **One shared manifest record per file:** `file`, `url`, `fetched_at` (the real
  download time, ISO-8601 with timezone), `sha256`, `bytes`, `status`, `ok`.
  Every fetcher writes it, and ingest reads it. The fetcher and the ingest are tested against each other:
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
- **Backend identity is a required variable, `WORDSWORTH_BACKEND_ENV`**
  (`homelab|alma`), read like `config.py`'s other environment settings but
  without a default: missing, empty or unknown is refused, and only `homelab`
  starts a manifest run. A declared value is auditable; a guess is not.
- **Own module for the manifest path.** `ingest_corpus.py` is 94 lines and
  must stay a CLI wrapper; the manifest logic goes in its own module so every
  file is ≤200 lines.
- **A layer that did not run is a failure.** A document that did not reach
  `indexed` because a layer did not run (OpenAnonymiser down included) fails the
  run; it is not reported as a success with a note. The exit status is non-zero.
- **Gate order is checked by the script, proven by git.** The script refuses a
  manifest whose pilot report has no completed check (who, when, quoted
  robots.txt and terms, Anubis status, decision `proceed`). Git order (check
  committed before manifest) is proven by the pilot report, not by the script.

## Rejected

- **A pilot-only ingest script.** It would drift from the first path.
- **Changing ingest to record provenance on re-delivery.** It changes a
  promise (what a document's provenance means once it exists); it needs its own
  OpenSpec change. Reported as a pilot finding.
- **Adding the dossier to the object key.** Same reason, and it would break
  one-document-per-object.
- **A host allow-list** to recognise homelab. It drifts as hosts change.
- **Resolving the backend hosts.** Both clusters use `*.svc.cluster.local`, so
  the names do not tell homelab from alma.
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
