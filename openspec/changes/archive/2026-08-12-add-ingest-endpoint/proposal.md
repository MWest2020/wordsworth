## Why

Ingestion is CLI/library-only (`wordsworth-ingest` reads a local `--corpus-dir`).
To run the straat on documents that live elsewhere (e.g. on a machine that can
reach the API over the tailnet but has no cluster/kubectl access and shouldn't
stage GBs through a bastion), there must be a way to push a document over HTTP.
Without it, the only path is staging files onto a PVC — which needs disk on the
bastion and a loader dance. An HTTP ingest endpoint makes the API the single
data-plane: the caller streams a PDF, the straat runs, done.

## What Changes

- `create_app` gains `store` + `anonymizer` parameters and registers
  **`POST /ingest`** when `session_factory`, `store`, `search_index` and
  `embedder` are all wired. The route accepts an uploaded PDF and drives the full
  pipeline — `ingest → OCR recovery (if scanned) → anonymize → store → index` —
  returning `{document_id, filename, state}`. The anonymizer defaults to the
  OpenAnonymiser (GLiNER) driver.
- Fail-hard, no leak: any failure (incl. the anonymizer service being down)
  returns `502` carrying only the error *class name*, never document text; an
  empty upload is `400`. The per-document transaction rolls back on failure.
- `serve.build_app` wires `store` + `anonymizer` only when S3 credentials are
  configured, so importing the module never requires secrets (read-only app
  without creds).
- Add `python-multipart` (required by FastAPI for file uploads).

## Capabilities

### Modified Capabilities
- `deployment`: the servable API gains an HTTP document-ingestion write path.

## Impact

- Code: `src/wordsworth/api.py` (route + params), `serve.py` (wiring),
  `pyproject.toml` (`python-multipart`). No change to the pipeline, the
  `Anonymizer` seam, or the read routes. The endpoint reuses `pipeline.ingest`,
  `pipeline.process` and `recovery.recover` unchanged.
- Deploy: the API pod already has the DB/S3/config env, so `/ingest` activates
  once the new image rolls out. Reachable over the tailnet-internal API.
