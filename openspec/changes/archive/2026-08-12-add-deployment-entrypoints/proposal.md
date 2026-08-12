## Why

Wordsworth was built library-/test-first and has **no runnable production
entrypoints**:

- **No composition root.** `create_app()` registers each route only if its
  dependency is injected; called with no args it serves **only `/health`**.
  There is no module-level `app`, so `uvicorn wordsworth.<x>:app` has nothing to
  serve and the real dependency graph (Postgres/OpenSearch/Ollama) is wired
  nowhere but tests.
- **No production ingestion entrypoint.** The pipeline (`ingest`/`process`) is
  library-only; the sole CLI (`scripts/eval/ingest_eval_corpus.py`) uses an
  in-memory store and the regex-only `DeterministicAnonymizer` — not S3 and not
  the OpenAnonymiser GLiNER driver. There is no way to run the full straat on a
  real corpus.
- **No schema bootstrap.** Tables + the append-only audit trigger are created by
  `init_schema`, whose only caller is that eval script. A deploy has no
  idempotent way to create the schema before serving.

To run the straat on real corpora on alma (Architecture A: anonymize via the
OpenAnonymiser GLiNER service over HTTP), these entrypoints must exist. This
change adds them, plus the container/K8s artifacts to deploy them.

## What Changes

- **`wordsworth.serve:app`** — API composition root. `build_app()` wires
  `create_app` to real backends from config (`make_session_factory`,
  `OpenSearchIndex`, `OllamaEmbedder`, `OllamaGenerator`), exposing the full read
  surface (document state, metrics, search, hybrid, ask). Backends are lazy —
  importing the module performs no network I/O; individual requests fail-hard.
- **`wordsworth-ingest`** (`wordsworth.ingest_corpus:main`) — runs the full
  straat over a directory of PDFs: `ingest → OCR recovery (if scanned) →
  anonymize (OpenAnonymiser GLiNER) → store (S3) → index (OpenSearch + Ollama
  bge-m3)`, using the sovereign backends from config. Explicitly wires
  `OpenAnonymiserAnonymizer`, not the regex-only default.
- **`wordsworth-init`** (`wordsworth.bootstrap:main`) — runs `init_schema`
  idempotently before serving/ingesting.
- **Deploy artifacts** (`deploy/`): a `Dockerfile` (Python 3.12, uv, git for the
  zeef source, tesseract-ocr + `tesseract-ocr-nld` + ghostscript for OCR
  recovery, non-root), K8s manifests (namespace, config/secret templates,
  init Job, API Deployment + Service, ingest Job), and a runbook.

## Capabilities

### Added Capabilities
- `deployment`: runnable composition roots — a servable API, a corpus-ingestion
  CLI running the full straat with the GLiNER anonymizer, and an idempotent
  schema bootstrap.

## Impact

- New modules: `src/wordsworth/serve.py`, `ingest_corpus.py`, `bootstrap.py`.
  `pyproject.toml` gains `[project.scripts]` (`wordsworth-init`,
  `wordsworth-ingest`). New `deploy/` tree (Dockerfile + K8s + runbook).
- No change to existing behavior: the pipeline, the `Anonymizer` seam, the API
  routes, and all other capabilities are untouched — this only *composes* them
  into runnable entrypoints. Secrets (DB URL, S3 keys) are injected via the
  environment (SOPS+age / OpenBao), never baked into image or manifests.
- Requires the sovereign backends provisioned on alma (Postgres, OpenSearch,
  Ollama with bge-m3, S3, and the OpenAnonymiser GLiNER service). No cloud in the
  critical path; no banned deps introduced.
