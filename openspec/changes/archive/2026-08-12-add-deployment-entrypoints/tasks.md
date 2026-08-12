## 1. API composition root

- [x] 1.1 `serve.py` `build_app()` wires create_app to real backends from config.
- [x] 1.2 Module-level `app = build_app()`; import performs no network I/O.
- [x] 1.3 Test: built app exposes the full route set (not health-only), offline.

## 2. Corpus ingestion entrypoint

- [x] 2.1 `ingest_corpus.py` runs ingest → OCR recovery → anonymize → store →
  index over a corpus dir, wiring S3 + OpenAnonymiser GLiNER + OpenSearch + Ollama.
- [x] 2.2 Uses `OpenAnonymiserAnonymizer` (not the regex-only default); fail-hard.
- [x] 2.3 `main()` argparse (`--corpus-dir`); test the missing-dir guard offline.

## 3. Schema bootstrap

- [x] 3.1 `bootstrap.py` `main()` runs `init_schema` idempotently.
- [x] 3.2 `[project.scripts]`: `wordsworth-init`, `wordsworth-ingest`.

## 4. Deploy artifacts

- [x] 4.1 `deploy/Dockerfile` (py3.12, uv, git, tesseract+nld+ghostscript, non-root).
- [x] 4.2 K8s: namespace, config/secret templates, init Job, API Deployment +
  Service, ingest Job.
- [x] 4.3 `deploy/README.md` runbook (build → push → init → serve → ingest on alma).

## 5. Gate

- [x] 5.1 Full suite green + `openspec validate --all`.
