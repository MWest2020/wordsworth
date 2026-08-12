## Why

Ingesting a directory meant one HTTP request per file and hand-rolled curl loops,
and the single-file endpoint aborted with a 502 on the first bad document. To run
a real corpus from a tailnet machine we want to (a) push many files per request
with per-file results that survive a bad document, and (b) have a proper client
instead of curl loops. FastAPI already serves interactive docs, but the routes
had no summaries.

## What Changes

- **`POST /ingest` accepts one or more files** (`files: list[UploadFile]`, field
  name `files`). Each is driven through the straat independently; a failing file
  is recorded (`state: "error"`, error *class* only — no text) and does **not**
  abort the batch. Response is `{total, indexed, results:[{filename, document_id,
  state, error}]}`. Fail-hard/no-leak preserved.
- **`wordsworthctl` client CLI** (stdlib-only, copy-runnable): `health`,
  `ingest <file|dir>` (recurses, `*.pdf` by default or `--all`, batches to
  `/ingest`, prints per-file results + summary), `search`, `state`. Base URL via
  `--url` / `$WORDSWORTH_API_URL`.
- **Nicer API docs**: title/description/version, per-route `summary` + docstrings,
  `read`/`write`/`ops` tags, and a typed `IngestResponse` model — all surfaced in
  `/docs` and `/openapi.json`.

## Capabilities

### Modified Capabilities
- `deployment`: the ingest endpoint is now batch + resilient; a client CLI is
  added for interacting with the API.

## Impact

- Code: `src/wordsworth/api.py` (batch route + response models + docs),
  `client.py` (new CLI), `pyproject.toml` (`wordsworthctl` script). No change to
  the pipeline or the `Anonymizer` seam. `serve.build_app` unchanged.
- Clients now upload with field name `files` (single or many): e.g.
  `curl -F files=@a.pdf -F files=@b.pdf .../ingest`, or `wordsworthctl ingest <dir>`.
