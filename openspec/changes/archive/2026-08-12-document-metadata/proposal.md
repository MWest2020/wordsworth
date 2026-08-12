## Why

The terminal output and API told you *that* a document was indexed, but not the
useful operational metadata — how long it took, how much PII was redacted, page
counts — and there was no way to query that back afterwards. All of it is already
recorded in the append-only audit chain (per-step timestamps + payloads); it just
wasn't exposed.

## What Changes

- **`GET /documents/{id}`** returns per-document metadata derived from the audit
  chain: current state, total + per-step processing **duration**, PII redaction
  **counts** (the anonymize step), page/byte metrics (the profile step), and the
  ordered step trail. 404 when the document is unknown. No schema change.
- **`/ingest` results carry metadata**: each per-file result now includes
  `duration_ms` and `counts`.
- **CLI**: new `wordsworth meta <id>`; the `ingest` output shows a compact
  suffix per file, e.g. `2130276.pdf: indexed (1.8s, bsn=1 person=2)`.

## Capabilities

### Modified Capabilities
- `deployment`: adds a queryable document-metadata endpoint; ingest results and
  the CLI expose timing + PII counts.

## Impact

- Code: `src/wordsworth/api.py` (`_document_meta` helper, `GET /documents/{id}`,
  enriched `IngestResult`), `client.py` (`meta` + richer `ingest` output). Docs
  (README + docs/reference/cli.md). No pipeline/schema change — all derived from
  existing `AuditRecord` rows (ts + payload).
