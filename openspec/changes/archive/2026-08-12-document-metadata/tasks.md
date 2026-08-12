## 1. Metadata endpoint

- [x] 1.1 `_document_meta` derives state, total + per-step duration, PII counts,
  page/byte metrics, and the step trail from `AuditRecord` rows.
- [x] 1.2 `GET /documents/{id}` returns it (404 when unknown).

## 2. Enriched ingest + CLI

- [x] 2.1 `IngestResult` carries `duration_ms` + `counts`; `_ingest_one` returns
  the metadata.
- [x] 2.2 CLI `meta` subcommand; `ingest` output shows duration + non-zero counts.

## 3. Docs + gate

- [x] 3.1 README + docs/reference/cli.md updated.
- [x] 3.2 Tests (route registration, `_result_extra` formatting) + full suite green.
