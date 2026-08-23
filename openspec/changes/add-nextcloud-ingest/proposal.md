## Why

Documents to run through the straat live in a Nextcloud (the operator's
canary/acceptance environment). Until now the only way in was uploading files to
`POST /ingest`. A pull-based Nextcloud source lets documents dropped in a
Nextcloud folder flow into Wordsworth automatically — the "Nextcloud
canary-accept" coupling — without changing the pipeline.

## What Changes

- **`nextcloud_source.py`** — a WebDAV client (`NextcloudClient`) that lists a
  Nextcloud folder (`PROPFIND`, recursive) and fetches file bytes, behind a
  `WebDavSource` protocol seam so it is testable without a live server. A pure
  driver `ingest_from_nextcloud(client, ingest_one, folder)` pulls each PDF and
  feeds it through the caller's per-document ingest closure, returning per-outcome
  counts. PDF-only; content-addressed idempotency and continue-on-failure are
  inherited from the existing ingest path.
- **`POST /ingest/nextcloud`** — mounts ONLY when a Nextcloud source is configured
  (mirrors the reveal/reprocess conditional mount); reuses the SAME `_ingest_one`
  closure as `POST /ingest`, so de-identification, the pseudonyms-only index and
  the idempotent skip are unchanged.
- **CLI `wordsworth ingest-nextcloud [--folder ...]`** triggers the pull; reports
  "not configured" (exit 2) when the endpoint is absent.
- **Config** `WORDSWORTH_NEXTCLOUD_{URL,USER,PASSWORD,FOLDER}` — all empty by
  default, so the feature is fully inert until configured. The app-password is
  used only for WebDAV Basic auth, never logged or committed.

## Capabilities

### Added Capabilities
- `nextcloud-ingest`: pull documents from a Nextcloud folder over WebDAV and drive
  them through the existing ingest+process straat; additive, default-off,
  idempotent, continue-on-failure.

## Impact

- Code: new `nextcloud_source.py`; `config.py` (+4 settings); `api.py` (one
  conditional endpoint reusing `_ingest_one`); `client.py` (one subcommand). No
  change to the pipeline, existing `/ingest`, or the index invariant. No new
  dependency (httpx + stdlib).
- Tests: pure (WebDAV XML parse, recursion, driver idempotency + continue-on-
  failure, inert-when-unconfigured, CLI) + DB-integration (end-to-end pull through
  the real pipeline). Local suite 259 passed.
- Wiring to a specific Nextcloud instance (URL + app-password Secret) is a deploy
  step, out of scope of this code change.
