# Runbook — Nextcloud ingest (pull-based canary/acceptance coupling)

Pull documents from a Nextcloud folder (over WebDAV) into the Wordsworth straat.
Additive and **default-off**: with no Nextcloud configured the endpoint is not
mounted and nothing changes.

## What it does

Lists the configured Nextcloud folder recursively, fetches each PDF, and drives it
through the normal pipeline (ingest → OCR-if-scanned → anonymize → index). It
reuses the same per-document ingest path as `POST /ingest`, so:
- the index holds only pseudonyms (de-identification is unchanged);
- it is **idempotent** — a file whose content is already indexed is skipped
  (content-addressed by sha256), so it is safe to re-run;
- it is **fault-tolerant** — a file that fails does not abort the run.

## Configure (operator, out-of-band)

Set on the wordsworth-api deployment (via a Secret for the password):

- `WORDSWORTH_NEXTCLOUD_URL`  — e.g. `https://cloud.example.org`
- `WORDSWORTH_NEXTCLOUD_USER` — the Nextcloud user
- `WORDSWORTH_NEXTCLOUD_PASSWORD` — a Nextcloud **app-password** (Settings →
  Security → Create new app password). Used only for WebDAV Basic auth; never
  logged or committed.
- `WORDSWORTH_NEXTCLOUD_FOLDER` — folder relative to the user's files root
  (default `/`).

When these are set, `POST /ingest/nextcloud` mounts automatically.

## Run

HTTP:
```
curl -s -X POST "$BASE/ingest/nextcloud?folder=/Woo"
```

CLI:
```
wordsworth ingest-nextcloud --folder /Woo
```

Both return per-outcome counts `{found, ingested, skipped, failed}`. Long-running
(GLiNER per document); safe to re-run — only what is missing from the index is
processed. If Nextcloud is not configured the CLI prints "not configured" (exit 2).
